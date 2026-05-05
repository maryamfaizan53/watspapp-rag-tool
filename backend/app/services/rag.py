import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import faiss_store
from app.db.models import Conversation, Message, DocumentChunk
from app.schemas.conversation import ConversationStatus
from app.services import embeddings, llm
from app.services.psx_tools import ALL_TOOLS

logger = logging.getLogger(__name__)

FALLBACK_LLM_DOWN = (
    "The AI service is temporarily unavailable. Please try again shortly."
)

SYSTEM_PROMPT = """You are a helpful PSX (Pakistan Stock Exchange) financial assistant.

You help investors with all PSX-related topics including:
- Live stock prices and KSE-100 index (use get_stock_price, get_kse100_index tools)
- Company fundamentals: market cap, P/E ratio, dividends (use get_company_info tool)
- Finding stock symbols by company name (use search_psx_symbol tool)
- How to open a PSX / CDC trading account (use web_search tool)
- Account opening requirements and documents (use web_search tool)
- Dividend announcements and payment dates (use web_search tool)
- Trade signals and market analysis (use web_search tool)
- SECP regulations, broker information, PSX rules (use web_search tool)

TOOL USAGE RULES — CRITICAL:
1. ALWAYS call a tool first before answering. Never write placeholder text like "[price here]" or "[insert data]".
2. For stock prices or KSE-100 — call get_stock_price or get_kse100_index. Use the real number returned.
3. For PSX procedures, account opening, dividends, regulations — call web_search with a specific query like "PSX CDC account opening requirements Pakistan 2024".
4. If the user gives a direct PSX symbol (e.g. ENGROH, OGDC, HBL, LUCK) — call get_stock_price immediately with that symbol. Do NOT call search_psx_symbol first.
4b. If the user gives a company name (e.g. "engro", "habib bank") — call search_psx_symbol to get the symbol, then call get_stock_price.
5. Use knowledge base context below when available — it may contain tenant-specific documents.
6. If the question is completely unrelated to finance or PSX, politely decline.
7. NEVER say "I couldn't find" or "I couldn't retrieve" — if web_search returns results, use them confidently. If it returns an error, answer from your knowledge without apologizing.

Knowledge base context (from uploaded documents):
{context}

Conversation history:
{history}

User question: {question}

Answer:"""


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
    """Full RAG pipeline: embed → search → prompt → generate with tools."""
    tid = str(tenant_id)
    cid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    # 1. Embed the query
    query_vector = embeddings.embed_text(query_text)

    # 2. FAISS similarity search (non-blocking — LLM+tools handle gaps)
    results = faiss_store.search(tid, query_vector, top_k=5)

    # 3. Fetch chunk texts from PostgreSQL
    context_parts = []
    chunk_ids_used = []

    for placeholder, _ in results:
        try:
            doc_id_str, chunk_idx_str = placeholder.split("_")
            did = UUID(doc_id_str)
            cidx = int(chunk_idx_str)
            query = select(DocumentChunk).where(
                DocumentChunk.document_id == did,
                DocumentChunk.chunk_index == cidx,
            )
            res = await db.execute(query)
            chunk = res.scalar_one_or_none()
            if chunk:
                context_parts.append(chunk.text)
                chunk_ids_used.append(str(chunk.id))
        except Exception:
            logger.warning("Failed to parse FAISS placeholder: %s", placeholder)

    # If no docs found, still proceed — tools and web search will cover the gaps
    context = (
        "\n\n".join(context_parts)
        if context_parts
        else "No documents uploaded yet. Use your tools and web search to answer."
    )

    # 4. Build conversation history string
    history_msgs = await _get_recent_history(db, cid)
    history_lines = []
    for msg in history_msgs:
        role = "User" if msg.role == "user" else "Assistant"
        text = msg.transcription or msg.content or ""
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines) if history_lines else "No prior conversation."

    # 5. Build prompt and call LLM with tools
    prompt = SYSTEM_PROMPT.format(context=context, history=history, question=query_text)
    answer = await llm.safe_generate_with_tools(prompt, ALL_TOOLS)

    if answer is None:
        return FALLBACK_LLM_DOWN, []

    return answer, chunk_ids_used
