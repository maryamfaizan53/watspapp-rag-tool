import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import faiss_store
from app.db.models import Conversation, Message, DocumentChunk
from app.schemas.conversation import ConversationStatus
from app.services import embeddings, llm

logger = logging.getLogger(__name__)

FALLBACK_NO_DATA = (
    "I don't have enough information in my knowledge base to answer that question. "
    "Please contact the administrator to upload relevant PSX documents."
)
FALLBACK_LLM_DOWN = (
    "The AI service is temporarily unavailable. Please try again shortly."
)

SYSTEM_PROMPT = """You are a helpful PSX (Pakistan Stock Exchange) financial assistant.
Answer questions ONLY about PSX-listed companies, stock market data, financial reports,
and related topics. If the question is not about PSX or financial markets, politely
decline and explain you only cover PSX-related topics.

Use the provided context to answer accurately. If the context does not contain enough
information, say so honestly rather than guessing.

Context:
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
    """Find the active session or create a new one (30-min inactivity rule)."""
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
        # Check if expired (30 mins)
        now = datetime.now(timezone.utc)
        last = conv.last_message_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        
        if (now - last).total_seconds() <= 1800:
            return conv

    # Create new conversation
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
    """Bump last_message_at and increment message_count."""
    cid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    
    query = (
        update(Conversation)
        .where(Conversation.id == cid)
        .values(
            last_message_at=datetime.now(timezone.utc),
            message_count=Conversation.message_count + 1
        )
    )
    await db.execute(query)
    await db.commit()


async def _get_recent_history(db: AsyncSession, conversation_id: UUID, limit: int = 5) -> list[Message]:
    """Fetch the last N messages from a conversation."""
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.timestamp))
        .limit(limit)
    )
    result = await db.execute(query)
    messages = list(result.scalars().all())
    messages.reverse()  # chronological order
    return messages


async def answer_query(
    db: AsyncSession,
    tenant_id: str | UUID,
    conversation_id: str | UUID,
    query_text: str,
) -> tuple[str, list[str]]:
    """
    Full RAG pipeline: embed → search → prompt → generate.
    Returns (answer_text, list_of_chunk_ids_used).
    """
    tid = str(tenant_id)
    cid = UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    # 1. Embed the query
    query_vector = embeddings.embed_text(query_text)

    # 2. FAISS similarity search
    results = faiss_store.search(tid, query_vector, top_k=5)
    if not results:
        return FALLBACK_NO_DATA, []

    # 3. Fetch chunk texts from PostgreSQL
    # results contains (placeholder_chunk_id, distance)
    # Our placeholder_chunk_id was f"{document_id}_{chunk_index}"
    # But we can also search by faiss_vector_id if we store it.
    # faiss_store returns the placeholder string we gave it.
    
    # Let's extract document_id and chunk_index from placeholder
    context_parts = []
    chunk_ids_used = []
    
    for placeholder, _ in results:
        try:
            doc_id_str, chunk_idx_str = placeholder.split("_")
            did = UUID(doc_id_str)
            cidx = int(chunk_idx_str)
            
            query = select(DocumentChunk).where(
                DocumentChunk.document_id == did,
                DocumentChunk.chunk_index == cidx
            )
            res = await db.execute(query)
            chunk = res.scalar_one_or_none()
            if chunk:
                context_parts.append(chunk.text)
                chunk_ids_used.append(str(chunk.id))
        except Exception:
            logger.warning("Failed to parse FAISS placeholder: %s", placeholder)

    context = "\n\n".join(context_parts)

    # 4. Build conversation history string
    history_msgs = await _get_recent_history(db, cid)
    history_lines = []
    for msg in history_msgs:
        role = "User" if msg.role == "user" else "Assistant"
        text = msg.transcription or msg.content or ""
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines) if history_lines else "No prior conversation."

    # 5. Build prompt and call LLM
    prompt = SYSTEM_PROMPT.format(context=context, history=history, question=query_text)
    answer = await llm.safe_generate(prompt)

    if answer is None:
        return FALLBACK_LLM_DOWN, []

    return answer, chunk_ids_used
