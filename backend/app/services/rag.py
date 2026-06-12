import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, desc

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import faiss_store
from app.db.models import Conversation, Message, DocumentChunk
from app.services import embeddings, llm
from app.services.psx_tools import ALL_TOOLS, _PSX_NAME_MAP, get_stock_price_by_query as _fetch_price

logger = logging.getLogger(__name__)

FALLBACK_LLM_DOWN = (
    "The AI service is temporarily unavailable. Please try again shortly."
)

NO_CONTEXT_MARKER = (
    "NO RELEVANT DOCUMENTS FOUND in the knowledge base for this question."
)

# Used when live stock data was pre-fetched in Python (LLM just formats the answer)
_PROMPT_WITH_LIVE_DATA = """You are an expert PSX (Pakistan Stock Exchange) financial assistant.

LIVE STOCK DATA (fetched right now — this is the ONLY price data you may use):
{live_data}

Knowledge base (uploaded documents):
{context}

Conversation history:
{history}

User question: {question}

STRICT RULES — follow exactly:
1. Use ONLY the LIVE STOCK DATA above for prices. For each company with a price: state name, symbol, current price in PKR, change, and percent change.
2. If an entry has status "unavailable" (or no price), say clearly that its live price could not be fetched right now. NEVER invent, estimate, or recall a price from memory.
3. Do not add companies that are not in the data.
4. For non-price parts of the question, answer ONLY from the knowledge base context above. If the context says no relevant documents were found, say you don't have that information in the knowledge base.
5. This is information only, not financial or investment advice.

Answer:"""

# Used when no stock was pre-fetched (LLM must call tools itself)
_PROMPT_WITH_TOOLS = """You are an expert PSX (Pakistan Stock Exchange) financial assistant.

TOOLS AVAILABLE:
- get_stock_price_by_query(query) — live PSX stock price. Pass EXACTLY what the user typed.
- get_kse100_index() — live KSE-100 index value.
- get_company_info(query) — market cap, P/E, EPS, 52-week high/low, dividend yield.
- web_search(query) — search web for PSX news, account procedures, dividends, regulations. NEVER for prices.

STRICT RULES — follow exactly:
1. ALWAYS call a tool first. Never write "[price]" or guessed numbers.
2. Stock price → get_stock_price_by_query(EXACT user text). KSE-100 → get_kse100_index(). Fundamentals → get_company_info(EXACT user text).
3. Account opening, dividends, regulations, news → web_search().
4. If a tool returns status "unavailable" or an error, tell the user that data could not be fetched right now. NEVER invent, estimate, or recall numbers from memory, and never pull prices out of web search text.
5. For questions about the uploaded documents, answer ONLY from the knowledge base context below. If the context says no relevant documents were found and no tool can answer, say you don't have that information.
6. Use successful tool results directly and confidently. Do not hedge on data you actually fetched.
7. Off-topic (non-finance) → politely decline.
8. This is information only, not financial or investment advice.

Knowledge base (uploaded documents):
{context}

Conversation history:
{history}

User question: {question}

Answer:"""


def _format_price_direct(live_data: str) -> str | None:
    """Format pre-fetched price data in Python when LLM is unavailable."""
    lines = []
    for block in live_data.split("\n---\n"):
        block = block.strip()
        if not block:
            continue
        try:
            d = json.loads(block)
            sym = d.get("symbol", "")
            name = d.get("company_name", sym)
            price = d.get("current_price_pkr")
            change = d.get("change_pkr")
            pct = d.get("change_percent")
            source = d.get("source", "")
            if price is None:
                if sym:
                    lines.append(f"*{sym}*\nLive price unavailable right now — please try again shortly.")
                continue
            arrow = "▲" if (change or 0) >= 0 else "▼"
            line = f"*{name} ({sym})*\nPrice: PKR {price}"
            if change is not None and pct is not None:
                line += f"\nChange: {arrow} PKR {abs(change)} ({abs(pct)}%)"
            if source:
                line += f"\n_Source: {source}_"
            lines.append(line)
        except Exception:
            pass
    if not lines:
        return None
    header = "Latest PSX price:\n\n" if len(lines) == 1 else "Latest PSX prices:\n\n"
    return header + "\n\n".join(lines)


def _extract_all_symbols(query_text: str) -> list[str]:
    """
    Scan the full query and return ALL matching PSX symbols (deduplicated, order-preserving).
    Uses exact match first, then whole-word regex — same logic as _resolve_symbol but for ALL matches.
    """
    q = query_text.lower()
    found: dict[str, bool] = {}  # symbol → seen (ordered dict behaviour in py3.7+)

    for key, sym in _PSX_NAME_MAP.items():
        if re.search(r'\b' + re.escape(key) + r'\b', q):
            found[sym] = True

    return list(found.keys())


async def _prefetch_stock_data(query_text: str) -> str:
    """
    Find ALL PSX companies mentioned in the query and pre-fetch their prices in parallel.
    Returns a multi-company JSON string, or "" if no known stocks found.

    Results with status="unavailable" are INCLUDED on purpose — the prompt
    instructs the model to relay the unavailability instead of guessing.
    """
    symbols = _extract_all_symbols(query_text)
    if not symbols:
        return ""

    logger.info("Pre-fetching prices for: %s", symbols)
    tasks = [_fetch_price(sym) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    data_parts = []
    for sym, result in zip(symbols, results):
        if isinstance(result, Exception):
            logger.warning("Pre-fetch error for %s: %s", sym, result)
            data_parts.append(json.dumps({
                "symbol": sym, "status": "unavailable",
                "error": "Live price could not be fetched right now.",
            }, indent=2))
        elif isinstance(result, dict):
            data_parts.append(json.dumps(result, indent=2))

    return "\n---\n".join(data_parts) if data_parts else ""


async def get_or_create_conversation(
    db: AsyncSession,
    tenant_id: str | UUID,
    bot_user_id: str | UUID,
    platform: str,
) -> Conversation:
    tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    buid = UUID(bot_user_id) if isinstance(bot_user_id, str) else bot_user_id

    query = (
        select(Conversation)
        .where(Conversation.tenant_id == tid, Conversation.bot_user_id == buid)
        .order_by(desc(Conversation.last_message_at))
        .limit(1)
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if conv:
        now = datetime.now(timezone.utc)
        last = conv.last_message_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() <= 1800:
            return conv

    new_conv = Conversation(
        tenant_id=tid,
        bot_user_id=buid,
        platform=platform,
        started_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        message_count=0,
        status="active",
    )
    db.add(new_conv)
    await db.commit()
    await db.refresh(new_conv)
    return new_conv


async def update_conversation(db: AsyncSession, conversation_id: str | UUID) -> None:
    cid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    query = (
        update(Conversation)
        .where(Conversation.id == cid)
        .values(
            last_message_at=datetime.now(timezone.utc),
            message_count=Conversation.message_count + 1,
        )
    )
    await db.execute(query)
    await db.commit()


async def _get_recent_history(db: AsyncSession, conversation_id: UUID, limit: int = 5) -> list[Message]:
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.timestamp))
        .limit(limit)
    )
    result = await db.execute(query)
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def answer_query(
    db: AsyncSession,
    tenant_id: str | UUID,
    conversation_id: str | UUID,
    query_text: str,
) -> tuple[str, list[str]]:
    """Full RAG pipeline: embed → search → relevance filter → (pre-fetch or tools) → generate."""
    tid = str(tenant_id)
    cid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    # 1. Embed the query
    query_vector = embeddings.embed_text(query_text)

    # 2. FAISS similarity search
    results = faiss_store.search(tid, query_vector, top_k=5)

    # 2b. RELEVANCE FILTER — without this, the 5 nearest chunks are injected
    # as "context" no matter how far away they are, and the model treats
    # irrelevant text as ground truth. Chunks beyond the distance threshold
    # are discarded; if nothing survives, the prompt explicitly says so.
    relevant = [(pid, dist) for pid, dist in results if dist <= settings.rag_max_distance]
    if results and not relevant:
        logger.info(
            "FAISS hits for tenant %s all above distance threshold %.2f (best=%.3f) — treating as no context",
            tid, settings.rag_max_distance, results[0][1],
        )

    # 3. Fetch chunk texts from PostgreSQL
    context_parts = []
    chunk_ids_used = []

    for placeholder, _dist in relevant:
        try:
            doc_id_str, chunk_idx_str = placeholder.rsplit("_", 1)
            did = UUID(doc_id_str)
            cidx = int(chunk_idx_str)
            q = select(DocumentChunk).where(
                DocumentChunk.document_id == did,
                DocumentChunk.chunk_index == cidx,
            )
            res = await db.execute(q)
            chunk = res.scalar_one_or_none()
            if chunk:
                context_parts.append(chunk.text)
                chunk_ids_used.append(str(chunk.id))
        except Exception:
            logger.warning("Failed to parse FAISS placeholder: %s", placeholder)

    context = "\n\n".join(context_parts) if context_parts else NO_CONTEXT_MARKER

    # 4. Build conversation history string
    history_msgs = await _get_recent_history(db, cid)
    history_lines = []
    for msg in history_msgs:
        role = "User" if msg.role == "user" else "Assistant"
        text = msg.transcription or msg.content or ""
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines) if history_lines else "No prior conversation."

    # 5. Try to pre-fetch stock data in Python (bypasses LLM symbol resolution errors)
    live_data = await _prefetch_stock_data(query_text)

    if live_data:
        # Data already fetched — LLM just formats it, no tools needed
        prompt = _PROMPT_WITH_LIVE_DATA.format(
            live_data=live_data, context=context, history=history, question=query_text
        )
        answer = await llm.safe_generate(prompt)
        if answer is None:
            # LLM is down but we have the price data — format it directly in Python
            answer = _format_price_direct(live_data)
    else:
        # Unknown stock or non-stock query — let LLM pick the right tool
        prompt = _PROMPT_WITH_TOOLS.format(
            context=context, history=history, question=query_text
        )
        answer = await llm.safe_generate_with_tools(prompt, ALL_TOOLS, force_tool=True)

    if answer is None:
        return FALLBACK_LLM_DOWN, []

    return answer, chunk_ids_used
