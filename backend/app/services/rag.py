import logging
from datetime import datetime, timezone

from bson import ObjectId

from app.db import faiss_store
from app.db.mongo import get_db
from app.models.conversation import Conversation
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
    tenant_id: str,
    bot_user_id: str,
    platform: str,
) -> Conversation:
    """Find the active session or create a new one (30-min inactivity rule)."""
    db = get_db()
    doc = await db.conversations.find_one(
        {"tenant_id": ObjectId(tenant_id), "bot_user_id": ObjectId(bot_user_id)},
        sort=[("last_message_at", -1)],
    )

    if doc:
        doc["_id"] = str(doc["_id"])
        doc["tenant_id"] = str(doc["tenant_id"])
        doc["bot_user_id"] = str(doc["bot_user_id"])
        conv = Conversation(**doc)
        if not conv.is_expired():
            return conv

    # Create new conversation
    new_conv = Conversation(
        tenant_id=tenant_id,
        bot_user_id=bot_user_id,
        platform=platform,
    )
    result = await db.conversations.insert_one(new_conv.to_doc())
    new_conv.id = str(result.inserted_id)
    return new_conv


async def update_conversation(conversation_id: str) -> None:
    """Bump last_message_at and increment message_count."""
    db = get_db()
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {"last_message_at": datetime.now(timezone.utc)},
            "$inc": {"message_count": 1},
        },
    )


async def _get_recent_history(conversation_id: str, limit: int = 5) -> list[dict]:
    """Fetch the last N messages from a conversation."""
    db = get_db()
    cursor = (
        db.messages.find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    docs.reverse()  # chronological order
    return docs


async def answer_query(
    tenant_id: str,
    conversation_id: str,
    query_text: str,
) -> tuple[str, list[str]]:
    """
    Full RAG pipeline: embed → search → prompt → generate.
    Returns (answer_text, list_of_chunk_ids_used).
    """
    # 1. Embed the query
    query_vector = embeddings.embed_text(query_text)

    # 2. FAISS similarity search
    results = faiss_store.search(tenant_id, query_vector, top_k=5)
    if not results:
        return FALLBACK_NO_DATA, []

    # 3. Fetch chunk texts from MongoDB
    db = get_db()
    chunk_ids = [chunk_id for chunk_id, _ in results]
    cursor = db.document_chunks.find(
        {"_id": {"$in": [ObjectId(cid) for cid in chunk_ids]}}
    )
    chunk_docs = await cursor.to_list(length=10)
    context = "\n\n".join(doc["text"] for doc in chunk_docs)

    # 4. Build conversation history string
    history_docs = await _get_recent_history(conversation_id)
    history_lines = []
    for msg in history_docs:
        role = "User" if msg["role"] == "user" else "Assistant"
        text = msg.get("transcription") or msg.get("content", "")
        history_lines.append(f"{role}: {text}")
    history = "\n".join(history_lines) if history_lines else "No prior conversation."

    # 5. Build prompt and call LLM
    prompt = SYSTEM_PROMPT.format(context=context, history=history, question=query_text)
    answer = await llm.safe_generate(prompt)

    if answer is None:
        return FALLBACK_LLM_DOWN, []

    return answer, chunk_ids
