import uuid
from datetime import datetime, timezone, date
from typing import Optional, List

from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, ForeignKey, Text,
    UniqueConstraint, Index, JSON, Float, Date
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.postgres import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="starter")
    status: Mapped[str] = mapped_column(String(50), default="active")

    # Channel config stored as JSON
    channels: Mapped[dict] = mapped_column(JSON, default=dict)

    # Quota stored as JSON
    quota: Mapped[dict] = mapped_column(JSON, default=lambda: {
        "messages_per_month": 5000,
        "rate_limit_per_minute": 60
    })

    # Usage stored as JSON
    usage: Mapped[dict] = mapped_column(JSON, default=lambda: {
        "message_count_month": 0,
        "active_users_month": 0
    })

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_tenants_status', 'status'),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="super_admin")
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class BotUser(Base):
    __tablename__ = "bot_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # telegram | whatsapp
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Telegram chat_id or WhatsApp number
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('tenant_id', 'platform', 'platform_id', name='uq_bot_user_platform'),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    bot_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bot_users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")

    __table_args__ = (
        Index('idx_conv_tenant_bot_lastmsg', 'tenant_id', 'bot_user_id', 'last_message_at'),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user | bot
    content_type: Mapped[str] = mapped_column(String(50), default="text")  # text | audio
    content: Mapped[str] = mapped_column(Text, nullable=False)
    transcription: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rag_context_ids: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index('idx_msg_conversation_time', 'conversation_id', 'timestamp'),
        Index('idx_msg_tenant_time', 'tenant_id', 'timestamp'),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | processing | ready | failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_doc_tenant_status', 'tenant_id', 'status'),
        UniqueConstraint('tenant_id', 'content_hash', name='uq_doc_tenant_hash'),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    faiss_vector_id: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_chunk_doc_index', 'document_id', 'chunk_index'),
        Index('idx_chunk_tenant', 'tenant_id'),
    )


class UsageSnapshot(Base):
    __tablename__ = "usage_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    voice_message_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'date', name='uq_usage_tenant_date'),
    )
