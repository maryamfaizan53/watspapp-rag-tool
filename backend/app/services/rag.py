import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import faiss_store
from app.db.models import Conversation, Message, DocumentChunk
from app.services import embeddings, llm
from app.services.psx_tools import ALL_TOOLS, _resolve_symbol, _yf_price, web_search as _web_search, _KNOWN_PSX_SYMBOLS, _CURRENT_YEAR

logger = logging.getLogger(__name__)

FALLBACK_LLM_DOWN = (
    "The AI service is temporarily unavailable. Please try again shortly."
)

# Used when live stock data was pre-fetched in Python (LLM just formats the answer)
_PROMPT_WITH_LIVE_DATA = """You are an expert PSX (Pakistan Stock Exchange) financial assistant.

LIVE STOCK DATA (fetched right now — use this in your answer):
{live_data}

Knowledge base (uploaded documents):
{context}

Conversation history:
{history}

User question: {question}

Answer using the LIVE STOCK DATA above. Be direct: state the company name, current price in PKR, change, and percent change. If web search results are shown instead of a price, extract and summarise the price information from them.

Answer:"""

# Used when no stock was pre-fetched (LLM must call tools itself)
_PROMPT_WITH_TOOLS = """You are an expert PSX (Pakistan Stock Exchange) financial assistant.

TOOLS AVAILABLE:
- get_stock_price_by_query(query) — live PSX stock price. Pass EXACTLY what the user typed.
- get_kse100_index() — live KSE-100 index value.
- get_company_info(query) — market cap, P/E, EPS, 52-week high/low, dividend yield.
- web_search(query) — search web for PSX news, account procedures, dividends, regulations.

RULES:
1. ALWAYS call a tool first. Never write "[price]" or guessed numbers.
2. Stock price → get_stock_price_by_query(EXACT user text).
3. KSE-100 → get_kse100_index().
4. Company fundamentals → get_company_info(EXACT user text).
5. Account opening, dividends, regulations, news → web_search().
6. Use tool results directly and confidently. Do not hedge or apologise.
7. Off-topic (non-finance) → politely decline.

Knowledge base (uploaded documents):
{context}

Conversation history:
{history}

User question: {question}

Answer:"""


async def _prefetch_stock_data(query_text: str) -> str:
    """
    Detect a known PSX company in the query and pre-fetch its price in Python.
    Returns a JSON/text string with the data, or "" if no known stock was found.
    This bypasses the LLM's tendency to 'correct' company names before tool calls.
    """
    resolved = _resolve_symbol(query_text)
    if resolved not in _KNOWN_PSX_SYMBOLS:
        return ""

    logger.info("Pre-fetching price for resolved symbol: %s (query: %s)", resolved, query_text)

    price = await _yf_price(resolved)
    if price:
        return json.dumps(price, indent=2)

    # YF unavailable — fall back to web search
    search = await _web_search(
        f"{resolved} share price PSX Pakistan today {_CURRENT_YEAR}", max_results=3
    )
    if "results" in search:
        return f"symbol: {resolved}\nsource: web search\n\n{search['results']}"

    return ""


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
    """Full RAG pipeline: embed → search → (pre-fetch or tools) → generate."""
    tid = str(tenant_id)
    cid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    # 1. Embed the query
    query_vector = embeddings.embed_text(query_text)

    # 2. FAISS similarity search
    results = faiss_store.search(tid, query_vector, top_k=5)

    # 3. Fetch chunk texts from PostgreSQL
    context_parts = []
    chunk_ids_used = []

    for placeholder, _ in results:
        try:
            doc_id_str, chunk_idx_str = placeholder.split("_")
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

    context = (
        "\n\n".join(context_parts)
        if context_parts
        else "No documents uploaded yet."
    )

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
        # Data is ready — LLM just formats the answer, no forced tool call needed
        prompt = _PROMPT_WITH_LIVE_DATA.format(
            live_data=live_data, context=context, history=history, question=query_text
        )
        answer = await llm.safe_generate_with_tools(prompt, ALL_TOOLS, force_tool=False)
    else:
        # Unknown stock or non-stock query — let LLM pick the right tool
        prompt = _PROMPT_WITH_TOOLS.format(
            context=context, history=history, question=query_text
        )
        answer = await llm.safe_generate_with_tools(prompt, ALL_TOOLS, force_tool=True)

    if answer is None:
        return FALLBACK_LLM_DOWN, []

    return answer, chunk_ids_used
