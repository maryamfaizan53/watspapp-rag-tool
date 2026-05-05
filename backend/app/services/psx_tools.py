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


# ── Public tools ──────────────────────────────────────────────────────────────

async def get_stock_price_by_query(query: str) -> dict:
    """Get live PSX stock price for any company name or symbol with automatic fallback."""
    symbol = _resolve_symbol(query)
    logger.info("get_stock_price_by_query: query=%s resolved=%s", query, symbol)

    # 1. Try Yahoo Finance
    result = await _yf_price(symbol)
    if result:
        return result

    # 2. Fallback: targeted web search
    logger.info("YF failed for %s — using web search fallback", symbol)
    search = await web_search(
        f"{symbol} share price PSX Pakistan today {_CURRENT_YEAR}",
        max_results=4,
    )
    if "results" in search:
        return {
            "symbol": symbol,
            "source": "web_search",
            "note": f"Live API data unavailable for {symbol}. Latest info from web:",
            "results": search["results"],
        }
    return {"error": f"Could not fetch price for '{query}' ({symbol}). The stock may not be listed or market is closed."}


async def get_kse100_index() -> dict:
    """Get the current live value of the KSE-100 index."""
    for symbol in ["^KRSE", "^KSE100", "PSX.KA"]:
        try:
            data = await _yf_fetch(symbol)
            results = data.get("chart", {}).get("result")
            if not results:
                continue
            meta = results[0]["meta"]
            current = round(meta.get("regularMarketPrice", 0), 2)
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

    # Fallback to web search
    search = await web_search(f"KSE-100 index value today Pakistan {_CURRENT_YEAR}", max_results=3)
    if "results" in search:
        return {"index": "KSE-100", "source": "web_search", "results": search["results"]}
    return {"error": "KSE-100 data unavailable. Check https://dps.psx.com.pk"}


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

    # Fallback to web search
    search = await web_search(
        f"{symbol} PSX company fundamentals market cap PE ratio dividend {_CURRENT_YEAR}",
        max_results=4,
    )
    if "results" in search:
        return {
            "symbol": symbol,
            "source": "web_search",
            "note": f"Fundamentals API unavailable for {symbol}. Latest info from web:",
            "results": search["results"],
        }
    return {"error": f"Could not fetch company info for '{query}' ({symbol})."}


async def web_search(query: str, max_results: int = 4) -> dict:
    """Search the web for PSX information: account opening, dividends, regulations, news, prices."""
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
                    "Handles symbol resolution, Yahoo Finance, and web search fallback automatically."
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
                    "Search the web for any PSX topic: account opening, dividends, regulations, broker info, "
                    "market news, trade signals, or any question not answerable by other tools."
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
                "Handles symbol resolution, Yahoo Finance, and web search fallback automatically."
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
                "Search the web for any PSX topic: account opening, dividends, regulations, broker info, "
                "market news, trade signals, or any question not answerable by other tools."
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
