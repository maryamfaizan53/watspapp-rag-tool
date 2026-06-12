import asyncio
import logging
import re
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

_CURRENT_YEAR = datetime.now().year

# Expanded PSX name→symbol map (exact match takes priority)
_PSX_NAME_MAP = {
    # Energy & Oil
    "ogdcl": "OGDC", "oil and gas development": "OGDC", "ogdc": "OGDC",
    "pso": "PSO", "pakistan state oil": "PSO",
    "ppl": "PPL", "pakistan petroleum": "PPL",
    "mari": "MARI", "mari petroleum": "MARI",
    "pol": "POL", "pakistan oilfields": "POL",
    "parco": "PARCO", "pak arab refinery": "PARCO",
    "nrl": "NRL", "national refinery": "NRL",
    "atrl": "ATRL", "attock refinery": "ATRL",
    # Power
    "hubc": "HUBC", "hub power": "HUBC",
    "kapco": "KAPCO", "kot addu power": "KAPCO",
    "ncpl": "NCPL", "nishat chunian power": "NCPL",
    "pkgp": "PKGP",
    # Banks
    "hbl": "HBL", "habib bank": "HBL",
    "mcb": "MCB", "mcb bank": "MCB",
    "ubl": "UBL", "united bank": "UBL",
    "bafl": "BAFL", "bank alfalah": "BAFL",
    "abl": "ABL", "allied bank": "ABL",
    "nbp": "NBP", "national bank": "NBP",
    "bahl": "BAHL", "bank al habib": "BAHL",
    "mebl": "MEBL", "meezan bank": "MEBL",
    "scbpl": "SCBPL", "standard chartered": "SCBPL",
    "silk": "SILK", "silkbank": "SILK",
    "jsbl": "JSBL", "js bank": "JSBL",
    # Chemicals / Fertilizers
    "engro": "ENGRO", "engro corporation": "ENGRO",
    "engroh": "ENGROH", "engro holdings": "ENGROH",
    "ffc": "FFC", "fauji fertilizer": "FFC",
    "ffbl": "FFBL", "fauji fertilizer bin qasim": "FFBL",
    "efert": "EFERT", "engro fertilizers": "EFERT",
    "fatima": "FATIMA", "fatima fertilizer": "FATIMA",
    "dawh": "DAWH", "dawood hercules": "DAWH",
    # Cement
    "luck": "LUCK", "lucky cement": "LUCK",
    "dgkc": "DGKC", "dg khan cement": "DGKC",
    "mlcf": "MLCF", "maple leaf cement": "MLCF",
    "pioc": "PIOC", "pioneer cement": "PIOC",
    "acpl": "ACPL", "attock cement": "ACPL",
    "chcc": "CHCC", "cherat cement": "CHCC",
    "fccl": "FCCL", "fauji cement": "FCCL",
    "kohc": "KOHC", "kohat cement": "KOHC",
    # Autos
    "psmc": "PSMC", "pak suzuki": "PSMC",
    "indu": "INDU", "indus motor": "INDU",
    "hcar": "HCAR", "honda atlas": "HCAR",
    "sazew": "SAZEW", "sazgar": "SAZEW",
    # Telecom
    "ptcl": "PTC", "pakistan telecom": "PTC",
    "trg": "TRG", "trg pakistan": "TRG",
    "wtl": "WTL", "worldcall": "WTL",
    # Consumer / Food
    "nestle": "NESTLE", "nestle pakistan": "NESTLE",
    "unity": "UNITY", "unity foods": "UNITY",
    "colg": "COLG", "colgate palmolive": "COLG",
    "ffl": "FFL", "fauji foods": "FFL",
    # Textiles
    "nml": "NML", "nishat mills": "NML",
    "ncl": "NCL", "nishat chunian": "NCL",
    "ktml": "KTML", "kohinoor textile": "KTML",
    # Tech / Other
    "avnc": "AVNC", "avanceon": "AVNC",
    "srvi": "SRVI", "services limited": "SRVI",
}


def _resolve_symbol(query: str) -> str:
    """Resolve company name or symbol to PSX ticker. Exact match first, then whole-word match."""
    q = query.lower().strip()
    if q in _PSX_NAME_MAP:
        return _PSX_NAME_MAP[q]
    for key, sym in _PSX_NAME_MAP.items():
        # Only match on whole words to avoid 'engro' matching 'engroh'
        if re.search(r'\b' + re.escape(key) + r'\b', q):
            return sym
        if re.search(r'\b' + re.escape(q) + r'\b', key):
            return sym
    return query.upper()


# Set of all known PSX symbols — used by rag.py for pre-fetch detection
_KNOWN_PSX_SYMBOLS: set[str] = set(_PSX_NAME_MAP.values())

# ── Data fetchers ─────────────────────────────────────────────────────────────
#
# ANTI-HALLUCINATION POLICY:
# Only STRUCTURED sources (JSON fields with named keys) may produce a price.
# The old broad HTML regexes (e.g. any <td>123.45</td> on a broker page, or
# "any number near 'PKR' in web-search snippets") could capture volume, a
# 52-week high, or a different stock entirely — and the LLM would then relay
# that wrong price with full confidence. For a financial product, an honest
# "price unavailable right now" is always better than a maybe-wrong number.

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


async def _yf_fetch(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "5d"}
    async with httpx.AsyncClient(timeout=15.0, headers=_YF_HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def _yf_summary(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    params = {"modules": "summaryDetail,defaultKeyStatistics,assetProfile"}
    async with httpx.AsyncClient(timeout=15.0, headers=_YF_HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def _yf_price(symbol: str) -> dict | None:
    """Fetch price from Yahoo Finance. Returns None on failure."""
    ticker = f"{symbol}.KA"
    try:
        data = await _yf_fetch(ticker)
        result = data["chart"]["result"][0]
        meta = result["meta"]
        current = round(meta.get("regularMarketPrice", 0), 2)
        if not current:
            return None
        prev = round(meta.get("previousClose", current), 2)
        change = round(current - prev, 2)
        change_pct = round((change / prev) * 100, 2) if prev else 0.0
        return {
            "symbol": symbol,
            "company_name": meta.get("longName", symbol),
            "current_price_pkr": current,
            "previous_close_pkr": prev,
            "change_pkr": change,
            "change_percent": change_pct,
            "currency": meta.get("currency", "PKR"),
            "source": "Yahoo Finance",
        }
    except Exception as exc:
        logger.warning("YF price failed for %s: %s", symbol, exc)
        return None


def _to_float(value) -> float | None:
    try:
        f = float(str(value).replace(",", ""))
        return f if 1.0 < f < 200_000 else None
    except (ValueError, TypeError):
        return None


async def _psx_live_price(symbol: str) -> dict | None:
    """
    Fetch live PSX price from STRUCTURED sources only:
    1. PSX timeseries API (JSON)
    2. PSX quotes/snapshot endpoints (JSON, named keys only)
    Broad HTML/regex scraping has been removed on purpose (see policy above).
    """
    sym = symbol.upper()

    # ── 1. PSX timeseries API ────────────────────────────────────────────────
    for ts_url in [
        f"https://dps.psx.com.pk/timeseries/eod?q={sym}",
        f"https://dps.psx.com.pk/timeseries/eod?company={sym}",
        f"https://dps.psx.com.pk/timeseries/intraday?q={sym}",
    ]:
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=_BROWSER_HEADERS) as client:
                resp = await client.get(ts_url)
                if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                    data = resp.json()
                    rows = data if isinstance(data, list) else data.get("data", [])
                    if rows:
                        row = rows[-1]
                        price = None
                        for key in ("c", "close", "ldcp", "last", "price"):
                            price = _to_float(row.get(key))
                            if price:
                                break
                        if price:
                            prev = _to_float(row.get("o") or row.get("open") or row.get("prev")) or price
                            change = round(price - prev, 2)
                            pct = round((change / prev) * 100, 2) if prev else 0.0
                            logger.info("PSX timeseries price for %s: %.2f", sym, price)
                            return {
                                "symbol": sym,
                                "current_price_pkr": round(price, 2),
                                "previous_close_pkr": round(prev, 2),
                                "change_pkr": change,
                                "change_percent": pct,
                                "source": "PSX Live (dps.psx.com.pk)",
                            }
        except Exception as exc:
            logger.debug("PSX timeseries %s failed: %s", ts_url, exc)

    # ── 2. PSX quotes/snapshot JSON endpoints (named keys only) ─────────────
    psx_headers = {**_BROWSER_HEADERS, "Referer": "https://www.psx.com.pk/", "Origin": "https://www.psx.com.pk"}
    json_endpoints = [
        f"https://dps.psx.com.pk/quotes?company={sym}",
        f"https://dps.psx.com.pk/company/{sym}/json",
        f"https://www.psx.com.pk/api/equity/snapshot?symbol={sym}",
    ]
    json_price_keys = ["currentPrice", "ldcp", "LDCP", "close", "lastSale", "price", "ltp", "last", "cP", "CurrPrice"]

    for url in json_endpoints:
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=psx_headers) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                if "json" not in resp.headers.get("content-type", ""):
                    continue
                data = resp.json()
                item = data[0] if isinstance(data, list) and data else data
                if not isinstance(item, dict):
                    continue
                for key in json_price_keys:
                    price = _to_float(item.get(key) or item.get(key.lower()))
                    if price is None:
                        continue
                    prev = _to_float(item.get("previousClose") or item.get("prev")) or price
                    change = round(price - prev, 2)
                    pct = round((change / prev) * 100, 2) if prev else 0.0
                    logger.info("PSX JSON price for %s: %.2f (url=%s)", sym, price, url)
                    return {
                        "symbol": sym,
                        "company_name": item.get("companyName") or item.get("name") or sym,
                        "current_price_pkr": round(price, 2),
                        "previous_close_pkr": round(prev, 2),
                        "change_pkr": change,
                        "change_percent": pct,
                        "source": "PSX Live (psx.com.pk)",
                    }
        except Exception as exc:
            logger.debug("PSX JSON endpoint failed %s: %s", url, exc)

    return None


# ── Public tools ──────────────────────────────────────────────────────────────

async def get_stock_price_by_query(query: str) -> dict:
    """
    Get live PSX stock price. Priority: PSX live (structured) → Yahoo Finance.
    When both fail, return an explicit 'unavailable' status — NEVER a guessed
    number scraped from arbitrary web text.
    """
    symbol = _resolve_symbol(query)
    logger.info("get_stock_price_by_query: query=%s resolved=%s", query, symbol)

    result = await _psx_live_price(symbol)
    if result:
        return result
    logger.info("PSX live failed for %s — trying Yahoo Finance", symbol)

    result = await _yf_price(symbol)
    if result:
        return result

    logger.info("All structured price sources failed for %s", symbol)
    return {
        "symbol": symbol,
        "status": "unavailable",
        "error": (
            f"Live price for {symbol} is unavailable right now from PSX and Yahoo Finance. "
            "Tell the user the live price could not be fetched at the moment and to try again "
            "shortly or check https://dps.psx.com.pk — do NOT state or estimate any number."
        ),
    }


async def get_kse100_index() -> dict:
    """Get the current live value of the KSE-100 index (structured sources only)."""
    for symbol in ["^KRSE", "^KSE100", "PSX.KA"]:
        try:
            data = await _yf_fetch(symbol)
            results = data.get("chart", {}).get("result")
            if not results:
                continue
            meta = results[0]["meta"]
            current = round(meta.get("regularMarketPrice", 0), 2)
            if not current:
                continue
            prev = round(meta.get("previousClose", current), 2)
            change = round(current - prev, 2)
            change_pct = round((change / prev) * 100, 2) if prev else 0.0
            return {
                "index": "KSE-100",
                "current_value": current,
                "previous_close": prev,
                "change": change,
                "change_percent": change_pct,
                "source": "Yahoo Finance",
            }
        except Exception as exc:
            logger.warning("get_kse100_index(%s): %s", symbol, exc)

    return {
        "index": "KSE-100",
        "status": "unavailable",
        "error": (
            "Live KSE-100 value is unavailable right now. Tell the user the live index "
            "could not be fetched and to check https://dps.psx.com.pk — do NOT state or "
            "estimate any number."
        ),
    }


async def get_company_info(query: str) -> dict:
    """Get company fundamentals: market cap, P/E ratio, 52-week range, dividend yield."""
    symbol = _resolve_symbol(query)
    ticker = f"{symbol}.KA"
    try:
        data = await _yf_summary(ticker)
        modules = data["quoteSummary"]["result"][0]
        sd = modules.get("summaryDetail", {})
        ks = modules.get("defaultKeyStatistics", {})
        ap = modules.get("assetProfile", {})

        def val(d, key):
            v = d.get(key)
            if isinstance(v, dict):
                return v.get("fmt") or v.get("raw", "N/A")
            return v if v is not None else "N/A"

        return {
            "symbol": symbol,
            "sector": ap.get("sector", "N/A"),
            "industry": ap.get("industry", "N/A"),
            "market_cap_pkr": val(sd, "marketCap"),
            "pe_ratio": val(sd, "trailingPE"),
            "eps": val(ks, "trailingEps"),
            "52_week_high_pkr": val(sd, "fiftyTwoWeekHigh"),
            "52_week_low_pkr": val(sd, "fiftyTwoWeekLow"),
            "dividend_yield": val(sd, "dividendYield"),
            "source": "Yahoo Finance",
        }
    except Exception as exc:
        logger.warning("get_company_info YF failed for %s: %s", symbol, exc)

    return {
        "symbol": symbol,
        "status": "unavailable",
        "error": (
            f"Fundamentals for {symbol} are unavailable right now. Tell the user the data "
            "could not be fetched at the moment — do NOT state or estimate any figures."
        ),
    }


async def web_search(query: str, max_results: int = 4) -> dict:
    """
    Search the web for PSX information: account opening procedures, dividends,
    regulations, broker info, news. NOT used as a price source — prices come
    only from structured APIs (see anti-hallucination policy above).
    """
    try:
        from duckduckgo_search import DDGS

        def _search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _search)

        if not results:
            return {"error": "No results found for this query."}

        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nSummary: {r['body']}\nSource: {r['href']}")
        return {"results": "\n\n---\n\n".join(formatted)}
    except Exception as exc:
        logger.error("web_search(%s): %s", query, exc)
        return {"error": f"Web search failed: {exc}"}


# ── Tool declarations ─────────────────────────────────────────────────────────

GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_stock_price_by_query",
                "description": (
                    "Get the current live PSX stock price for any company name or symbol. "
                    "Pass EXACTLY what the user typed — e.g. 'engroh', 'habib bank', 'OGDC', 'lucky cement'. "
                    "If the result has status='unavailable', tell the user the live price could not be "
                    "fetched right now — never invent a number."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Company name or symbol as user typed it"}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_kse100_index",
                "description": "Get the current live KSE-100 index value. Use for market index, overall market performance questions.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_company_info",
                "description": (
                    "Get company fundamentals: market cap, P/E ratio, EPS, 52-week range, dividend yield, sector. "
                    "Pass the company name or symbol — e.g. 'OGDC', 'engro', 'lucky cement'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Company name or PSX symbol"}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "web_search",
                "description": (
                    "Search the web for PSX topics: account opening, dividends, regulations, broker info, "
                    "market news. Do NOT use it to find stock prices or index values — use the price tools, "
                    "and if those fail, say the data is unavailable."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Results to return (default 4)"},
                    },
                    "required": ["query"],
                },
            },
        ]
    }
]

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price_by_query",
            "description": (
                "Get the current live PSX stock price for any company name or symbol. "
                "Pass EXACTLY what the user typed — e.g. 'engroh', 'habib bank', 'OGDC', 'lucky cement'. "
                "If the result has status='unavailable', tell the user the live price could not be "
                "fetched right now — never invent a number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Company name or symbol as user typed it"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kse100_index",
            "description": "Get the current live KSE-100 index value. Use for market index or overall market performance questions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": (
                "Get company fundamentals: market cap, P/E ratio, EPS, 52-week range, dividend yield, sector. "
                "Pass the company name or symbol — e.g. 'OGDC', 'engro', 'lucky cement'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Company name or PSX symbol"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for PSX topics: account opening, dividends, regulations, broker info, "
                "market news. Do NOT use it to find stock prices or index values — use the price tools, "
                "and if those fail, say the data is unavailable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Results to return (default 4)"},
                },
                "required": ["query"],
            },
        },
    },
]

ALL_TOOLS = {
    "gemini": GEMINI_TOOLS,
    "openai": OPENAI_TOOLS,
}

TOOL_FUNCTIONS = {
    "get_stock_price_by_query": get_stock_price_by_query,
    "get_kse100_index": get_kse100_index,
    "get_company_info": get_company_info,
    "web_search": web_search,
}
