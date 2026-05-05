import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

_PSX_NAME_MAP = {
    "ogdcl": "OGDC", "oil and gas development": "OGDC", "ogdc": "OGDC",
    "pso": "PSO", "pakistan state oil": "PSO",
    "hbl": "HBL", "habib bank": "HBL",
    "mcb": "MCB", "mcb bank": "MCB",
    "ubl": "UBL", "united bank": "UBL",
    "luck": "LUCK", "lucky cement": "LUCK",
    "engro": "ENGRO", "engro corporation": "ENGRO",
    "engroh": "ENGROH", "engro holdings": "ENGROH",
    "ppl": "PPL", "pakistan petroleum": "PPL",
    "bafl": "BAFL", "bank alfalah": "BAFL",
    "ffc": "FFC", "fauji fertilizer": "FFC",
    "ffbl": "FFBL",
    "abl": "ABL", "allied bank": "ABL",
    "nbp": "NBP", "national bank": "NBP",
    "ptcl": "PTC", "pakistan telecom": "PTC",
    "mari": "MARI", "mari petroleum": "MARI",
    "nestle": "NESTLE", "nestle pakistan": "NESTLE",
    "hubc": "HUBC", "hub power": "HUBC",
    "kapco": "KAPCO",
    "psmc": "PSMC", "pak suzuki": "PSMC",
    "indu": "INDU", "indus motor": "INDU",
    "atrl": "ATRL", "attock refinery": "ATRL",
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


async def get_stock_price(symbol: str) -> dict:
    """Get current live stock price for a PSX listed company."""
    ticker = f"{symbol.upper()}.KA"
    try:
        data = await _yf_fetch(ticker)
        result = data["chart"]["result"][0]
        meta = result["meta"]
        current = round(meta.get("regularMarketPrice", 0), 2)
        prev = round(meta.get("previousClose", current), 2)
        change = round(current - prev, 2)
        change_pct = round((change / prev) * 100, 2) if prev else 0.0
        return {
            "symbol": symbol.upper(),
            "company_name": meta.get("longName", symbol.upper()),
            "current_price_pkr": current,
            "previous_close_pkr": prev,
            "change_pkr": change,
            "change_percent": change_pct,
            "currency": meta.get("currency", "PKR"),
        }
    except Exception as exc:
        logger.error("get_stock_price(%s): %s", symbol, exc)
        return {"error": f"Could not fetch price for '{symbol}'. Verify the PSX symbol (e.g. OGDC, HBL, PSO)."}


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
            }
        except Exception as exc:
            logger.warning("get_kse100_index(%s): %s", symbol, exc)
    return {
        "error": "KSE-100 index live data is currently unavailable. "
                 "Please check https://dps.psx.com.pk for the latest index value."
    }


async def get_company_info(symbol: str) -> dict:
    """Get detailed company info including market cap, P/E, 52-week range."""
    ticker = f"{symbol.upper()}.KA"
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
            "symbol": symbol.upper(),
            "sector": ap.get("sector", "N/A"),
            "industry": ap.get("industry", "N/A"),
            "market_cap_pkr": val(sd, "marketCap"),
            "pe_ratio": val(sd, "trailingPE"),
            "eps": val(ks, "trailingEps"),
            "52_week_high_pkr": val(sd, "fiftyTwoWeekHigh"),
            "52_week_low_pkr": val(sd, "fiftyTwoWeekLow"),
            "dividend_yield": val(sd, "dividendYield"),
            "currency": "PKR",
        }
    except Exception as exc:
        logger.error("get_company_info(%s): %s", symbol, exc)
        return {"error": f"Could not fetch company info for '{symbol}': {exc}"}


def _resolve_symbol(query: str) -> str:
    """Resolve a company name or symbol string to a PSX ticker. Returns the ticker (may still be wrong if unknown)."""
    q = query.lower().strip()
    if q in _PSX_NAME_MAP:
        return _PSX_NAME_MAP[q]
    for key, sym in _PSX_NAME_MAP.items():
        if key in q or q in key:
            return sym
    return query.upper()


async def search_psx_symbol(company_name: str) -> dict:
    """Find a PSX stock symbol from a company name."""
    symbol = _resolve_symbol(company_name)
    ticker = f"{symbol}.KA"
    try:
        data = await _yf_fetch(ticker)
        if data["chart"]["result"]:
            return {"symbol": symbol, "note": "Symbol resolved"}
    except Exception:
        pass
    return {
        "error": f"Could not find a PSX symbol for '{company_name}'. "
                 "Try the stock symbol directly (e.g. OGDC, HBL, PSO, MCB, LUCK)."
    }


async def get_stock_price_by_query(query: str) -> dict:
    """Get current PSX stock price from any company name or symbol. Handles resolution and fallback automatically."""
    symbol = _resolve_symbol(query)
    result = await get_stock_price(symbol)
    if "error" not in result:
        return result
    # Yahoo Finance failed — fall back to web search
    logger.warning("YF failed for %s, falling back to web_search", symbol)
    search = await web_search(f"{query} PSX stock price today PKR")
    if "results" in search:
        return {"symbol": symbol, "note": "Live API unavailable. Web search result below.", **search}
    return {"error": f"Could not fetch price for '{query}'. Market may be closed or symbol not listed on Yahoo Finance."}


async def web_search(query: str, max_results: int = 4) -> dict:
    """Search the web for current PSX information, account procedures, dividends, regulations, etc."""
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


# ── Gemini tool declarations ──────────────────────────────────────────────────

GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_stock_price_by_query",
                "description": (
                    "Get the current live PSX stock price for any company name or symbol. "
                    "Pass EXACTLY what the user said — e.g. 'engroh', 'habib bank', 'OGDC', 'lucky cement'. "
                    "This tool handles all symbol resolution and fallback automatically."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Exact company name or symbol as the user typed it"}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_kse100_index",
                "description": (
                    "Get the current live value of the KSE-100 index. "
                    "Use when asked about the market index, KSE-100, or overall market performance today."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_company_info",
                "description": (
                    "Get detailed company fundamentals: market cap, P/E ratio, 52-week high/low, "
                    "sector and dividend yield. Pass the PSX symbol e.g. OGDC, HBL, ENGRO, ENGROH."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "PSX stock symbol e.g. OGDC, PSO, HBL, ENGROH"}
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "web_search",
                "description": (
                    "Search the web for current PSX-related information. Use for: "
                    "how to open a PSX/CDC account, account opening requirements, dividend announcements, "
                    "trade signals, SECP regulations, broker information, or any PSX topic not covered by other tools."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query, e.g. 'how to open PSX account Pakistan 2024'"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Number of results to return (default 4)"
                        }
                    },
                    "required": ["query"],
                },
            },
        ]
    }
]

# ── OpenAI tool declarations ──────────────────────────────────────────────────

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price_by_query",
            "description": (
                "Get the current live PSX stock price for any company name or symbol. "
                "Pass EXACTLY what the user said — e.g. 'engroh', 'habib bank', 'OGDC', 'lucky cement'. "
                "This tool handles all symbol resolution and fallback automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Exact company name or symbol as the user typed it"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kse100_index",
            "description": "Get the current live value of the KSE-100 index.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get detailed company fundamentals: market cap, P/E ratio, 52-week high/low, dividend yield. Pass the PSX symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "PSX stock symbol e.g. OGDC, PSO, HBL, ENGROH"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current PSX-related information. Use for: "
                "how to open a PSX/CDC account, account opening requirements, dividend announcements, "
                "trade signals, SECP regulations, broker information, or any PSX topic not covered by other tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query e.g. 'how to open PSX trading account Pakistan 2024'"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results (default 4)"
                    }
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
