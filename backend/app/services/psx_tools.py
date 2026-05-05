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


async def _psx_live_price(symbol: str) -> dict | None:
    """
    Fetch live PSX price. Tries multiple sources in order:
    1. PSX EOD timeseries API  2. PSX quotes JSON  3. HTML scraping (broker sites)
    """
    sym = symbol.upper()
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # ── 1. PSX EOD timeseries API — most structured JSON response ─────────────
    for ts_url in [
        f"https://dps.psx.com.pk/timeseries/eod?q={sym}",
        f"https://dps.psx.com.pk/timeseries/eod?company={sym}",
        f"https://dps.psx.com.pk/timeseries/intraday?q={sym}",
    ]:
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, headers=browser_headers) as client:
                resp = await client.get(ts_url)
                if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
                    data = resp.json()
                    rows = data if isinstance(data, list) else data.get("data", [])
                    if rows:
                        row = rows[-1]
                        price = 0.0
                        for key in ("c", "close", "ldcp", "last", "price"):
                            if row.get(key):
                                try:
                                    price = float(str(row[key]).replace(",", ""))
                                    break
                                except (ValueError, TypeError):
                                    pass
                        if price > 1.0:
                            logger.info("PSX timeseries price for %s: %.2f (url=%s)", sym, price, ts_url)
                            prev = float(str(row.get("o") or row.get("open") or row.get("prev") or price).replace(",", ""))
                            change = round(price - prev, 2)
                            pct = round((change / prev) * 100, 2) if prev else 0.0
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

    # ── 2. PSX quotes/snapshot JSON endpoints ────────────────────────────────
    psx_headers = {**browser_headers, "Referer": "https://www.psx.com.pk/", "Origin": "https://www.psx.com.pk"}
    json_endpoints = [
        f"https://dps.psx.com.pk/quotes?company={sym}",
        f"https://dps.psx.com.pk/company/{sym}/json",
        f"https://www.psx.com.pk/api/equity/snapshot?symbol={sym}",
    ]
    json_price_keys = ["currentPrice", "ldcp", "LDCP", "close", "lastSale", "price", "ltp", "last", "cP", "CurrPrice"]

    for url in json_endpoints:
        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False, headers=psx_headers) as client:
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
                    val = item.get(key) or item.get(key.lower())
                    if val is None:
                        continue
                    try:
                        price = float(str(val).replace(",", ""))
                        if 1.0 < price < 200_000:
                            prev = float(str(item.get("previousClose") or item.get("prev") or price).replace(",", ""))
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
                    except (ValueError, TypeError):
                        pass
        except Exception as exc:
            logger.debug("PSX JSON endpoint failed %s: %s", url, exc)

    # ── 3. HTML scraping: PSX portal + broker sites (globally accessible) ─────
    html_sources = [
        (
            f"https://dps.psx.com.pk/company/{sym}",
            [
                r'"ldcp"\s*:\s*"?([\d.]+)"?',
                r'"currentPrice"\s*:\s*"?([\d.]+)"?',
                r'"close"\s*:\s*"?([\d.]+)"?',
                r'"ltp"\s*:\s*"?([\d.]+)"?',
                r'"cP"\s*:\s*"?([\d.]+)"?',
                r'LDCP[^<>]{0,30}>([\d,]+\.?\d*)',
            ],
        ),
        (
            f"https://scstrade.com/stockscreening/SS_CompanySnapShot.aspx?symbol={sym}",
            [
                r'Current Price[^<>]{0,30}>([\d,]+\.?\d*)',
                r'Last Sale[^<>]{0,30}>([\d,]+\.?\d*)',
                r'id="lblCurrentPrice"[^>]*>([\d,]+\.?\d*)',
                r'([\d,]+\.\d{2})</span>',
            ],
        ),
        (
            f"https://www.scstrade.com/stockscreening/SS_CompanySnapShot.aspx?symbol={sym}",
            [r'([\d,]+\.\d{2})'],
        ),
    ]
    for url, patterns in html_sources:
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False, headers=browser_headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                text = resp.text
                for pattern in patterns:
                    m = re.search(pattern, text, re.IGNORECASE)
                    if m:
                        try:
                            price = float(m.group(1).replace(",", ""))
                            if 1.0 < price < 200_000:
                                logger.info("PSX HTML price for %s: %.2f (url=%s)", sym, price, url)
                                return {"symbol": sym, "current_price_pkr": price, "source": "PSX Website"}
                        except ValueError:
                            pass
        except Exception as exc:
            logger.warning("PSX HTML fetch failed for %s (%s): %s", sym, url, exc)

    return None


async def _web_price_extract(symbol: str) -> dict | None:
    """
    Targeted web search + Python regex price extraction.
    Returns a price dict WITHOUT going through the LLM for formatting.
    Used when PSX live and Yahoo Finance both fail.
    """
    try:
        month_year = datetime.now().strftime("%B %Y")
        search = await web_search(
            f'"{symbol}" PSX share price today PKR Pakistan {month_year}',
            max_results=6,
        )
        text = search.get("results", "")
        if not text:
            return None

        price_patterns = [
            r'(?:PKR|Rs\.?)\s*([\d,]{2,7}\.?\d{0,2})',           # PKR 311.42
            r'([\d,]{2,7}\.\d{2})\s*(?:PKR|Rs)',                  # 311.42 PKR
            rf'{re.escape(symbol)}[^\n]{{0,80}}?([\d,]{{2,7}}\.\d{{2}})',  # OGDC ... 311.42
            r'(?:current price|close|last sale|ldcp)[^\n]{0,25}?([\d,]{2,7}\.?\d{0,2})',
        ]
        for pattern in price_patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    price = float(m.group(1).replace(",", ""))
                    if 10.0 < price < 200_000:
                        logger.info("Web search price extract for %s: %.2f", symbol, price)
                        return {
                            "symbol": symbol,
                            "current_price_pkr": round(price, 2),
                            "source": "Web Search",
                        }
                except ValueError:
                    pass
    except Exception as exc:
        logger.debug("_web_price_extract failed for %s: %s", symbol, exc)
    return None


# ── Public tools ──────────────────────────────────────────────────────────────

async def get_stock_price_by_query(query: str) -> dict:
    """Get live PSX stock price. Priority: PSX live → Yahoo Finance → web price extract → raw web search."""
    symbol = _resolve_symbol(query)
    logger.info("get_stock_price_by_query: query=%s resolved=%s", query, symbol)

    # 1. PSX live — official source (timeseries → JSON → HTML)
    result = await _psx_live_price(symbol)
    if result:
        return result
    logger.info("PSX live failed for %s — trying Yahoo Finance", symbol)

    # 2. Yahoo Finance — secondary (may be stale for some PSX stocks)
    result = await _yf_price(symbol)
    if result:
        return result
    logger.info("YF failed for %s — trying web price extraction", symbol)

    # 3. Web search + Python price extraction (bypasses LLM formatting)
    result = await _web_price_extract(symbol)
    if result:
        return result
    logger.info("Web price extract failed for %s — using raw web search", symbol)

    # 4. Raw web search — LLM formats the answer from text snippets
    search = await web_search(
        f"{symbol} PSX share price Pakistan today {_CURRENT_YEAR}",
        max_results=4,
    )
    if "results" in search:
        return {
            "symbol": symbol,
            "source": "web_search",
            "note": f"Live API unavailable for {symbol}. Price info from web search:",
            "results": search["results"],
        }
    return {"error": f"Could not fetch price for '{query}' ({symbol})."}


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

    # Fallback: try PSX website for index
    try:
        import re as _re
        _headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=10.0, verify=False, headers=_headers) as client:
            resp = await client.get("https://dps.psx.com.pk/")
            if resp.status_code == 200:
                m = _re.search(r'KSE.?100[^>]*>\s*([\d,]+\.?\d*)', resp.text, _re.IGNORECASE)
                if m:
                    value = float(m.group(1).replace(",", ""))
                    if value > 10000:
                        return {"index": "KSE-100", "current_value": value, "source": "PSX Website"}
    except Exception:
        pass
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
