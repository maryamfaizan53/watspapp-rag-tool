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


async def search_psx_symbol(company_name: str) -> dict:
    """Find a PSX stock symbol from a company name."""
    query = company_name.lower().strip()
    # Exact match first to avoid substring collisions (e.g. "engro" matching "engroh")
    if query in _PSX_NAME_MAP:
        return {"symbol": _PSX_NAME_MAP[query], "matched_name": query.title()}
    for key, symbol in _PSX_NAME_MAP.items():
        if key in query or query in key:
            return {"symbol": symbol, "matched_name": key.title()}
    ticker = f"{company_name.upper()}.KA"
    try:
        data = await _yf_fetch(ticker)
        if data["chart"]["result"]:
            return {"symbol": company_name.upper(), "note": "Direct symbol match"}
    except Exception:
        pass
    return {
        "error": f"Could not find a PSX symbol for '{company_name}'. "
                 "Try the stock symbol directly (e.g. OGDC, HBL, PSO, MCB, LUCK)."
    }


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
                "name": "get_stock_price",
                "description": (
                    "Get the current live stock price for a PSX listed company. "
                    "Use when asked about current price, today's price, or live price of a stock."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "PSX stock symbol e.g. OGDC, PSO, HBL, MCB, LUCK, ENGRO"}
                    },
                    "required": ["symbol"],
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
                    "Get detailed company info including market cap, P/E ratio, 52-week high/low, "
                    "sector and dividend yield for a PSX listed company."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "PSX stock symbol e.g. OGDC, PSO, HBL"}
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "search_psx_symbol",
                "description": "Find the PSX stock symbol for a company by its name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string", "description": "Company name e.g. 'Habib Bank', 'Lucky Cement'"}
                    },
                    "required": ["company_name"],
                },
            },
            {
                "name": "web_search",
                "description": (
                    "Search the web for current PSX-related information. Use for: "
                    "how to open a PSX/CDC account, account opening requirements, dividend announcements, "
                    "trade signals, SECP regulations, broker information, or any PSX topic not in the knowledge base."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query, e.g. 'how to open PSX account Pakistan 2024' or 'PSX dividend announcement OGDC'"
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
            "name": "get_stock_price",
            "description": "Get the current live stock price for a PSX listed company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "PSX stock symbol e.g. OGDC, PSO, HBL, MCB"}
                },
                "required": ["symbol"],
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
            "description": "Get detailed company info: market cap, P/E ratio, 52-week high/low, dividend yield.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "PSX stock symbol e.g. OGDC, PSO, HBL"}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_psx_symbol",
            "description": "Find the PSX stock symbol for a company by its name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Company name e.g. 'Habib Bank', 'Lucky Cement'"}
                },
                "required": ["company_name"],
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
                "trade signals, SECP regulations, broker information, or any PSX topic not in the knowledge base."
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
    "get_stock_price": get_stock_price,
    "get_kse100_index": get_kse100_index,
    "get_company_info": get_company_info,
    "search_psx_symbol": search_psx_symbol,
    "web_search": web_search,
}
