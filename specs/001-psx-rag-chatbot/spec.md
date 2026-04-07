# Feature Specification: PSX RAG Chatbot SaaS

**Feature Branch**: `001-psx-rag-chatbot`
**Created**: 2026-04-07
**Status**: Draft
**Input**: User description: "PSX RAG Chatbot SaaS — WhatsApp and Telegram bot with RAG pipeline for PSX stock market data, admin dashboard, multi-tenant client management, voice support, and Docker/AWS deployment."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Investor Asks a Stock Question via Telegram (Priority: P1)

An investor opens their Telegram app and sends a text message to the PSX chatbot asking
about a company's financials, stock price history, or market news. The bot retrieves the
most relevant PSX data using a RAG pipeline and responds in natural language within seconds.

**Why this priority**: This is the core value proposition of the product. Without accurate,
fast question-answering, no other feature matters. It represents the primary user journey
and the foundation for all downstream features.

**Independent Test**: Can be fully tested by sending a question (e.g., "What is the P/E
ratio of OGDC?") to the Telegram bot and verifying the response references correct PSX
data, without any admin or WhatsApp functionality required.

**Acceptance Scenarios**:

1. **Given** a registered Telegram bot is live, **When** a user sends a text question about
   a PSX-listed company, **Then** the bot replies with a factually grounded answer citing
   the relevant data within 10 seconds.
2. **Given** the user sends a question outside the PSX domain (e.g., "What is the weather?"),
   **When** the bot processes the message, **Then** the bot responds politely that it only
   covers PSX-related topics.
3. **Given** the RAG knowledge base is empty, **When** a user asks a question, **Then**
   the bot replies that no relevant data is currently available and suggests contacting
   the administrator.

---

### User Story 2 — Investor Sends a Voice Message and Gets a Response (Priority: P2)

An investor records a voice message asking about a stock. The bot transcribes the audio,
runs it through the RAG pipeline, and replies with a text answer.

**Why this priority**: Voice is the primary input method on WhatsApp and a significant
channel on Telegram. Supporting voice unlocks a broader, less tech-savvy user base.

**Independent Test**: Can be fully tested by sending a voice note to the bot and verifying
that a transcription is generated and a relevant answer is returned, without requiring
admin or analytics features.

**Acceptance Scenarios**:

1. **Given** a user sends a voice note in a supported language, **When** the bot receives
   it, **Then** the bot transcribes the audio and responds with a relevant text answer
   within 20 seconds.
2. **Given** a voice note is too long (over 5 minutes), **When** received, **Then** the
   bot notifies the user that the message exceeds the allowed duration.
3. **Given** the audio is unintelligible or silent, **When** transcription is attempted,
   **Then** the bot asks the user to resend a clearer message.

---

### User Story 3 — Admin Uploads PSX Documents to the Knowledge Base (Priority: P3)

An admin logs into the web dashboard, uploads PDF or text documents (e.g., annual
reports, company filings, market summaries), and the system processes them into the
RAG knowledge base so the chatbot can answer queries against the new content.

**Why this priority**: The chatbot is only as good as its data. Admins need a reliable
way to keep the knowledge base current without developer intervention.

**Independent Test**: Can be fully tested by uploading a sample PSX document via the
admin dashboard and then asking the bot a question whose answer appears only in that
document.

**Acceptance Scenarios**:

1. **Given** an admin is logged in, **When** they upload a PDF or text file via the
   dashboard, **Then** the system confirms ingestion and the document content becomes
   queryable by the bot within 5 minutes.
2. **Given** an invalid file format is uploaded (e.g., `.exe`), **When** submitted,
   **Then** the dashboard shows a clear error indicating accepted formats.
3. **Given** a document is already in the knowledge base, **When** re-uploaded,
   **Then** the system deduplicates and updates the existing entry without creating
   duplicate results.

---

### User Story 4 — Admin Creates and Manages a Client Tenant (Priority: P4)

A SaaS operator creates a new client account through the admin dashboard, configures
their bot channels (Telegram token, WhatsApp number), and sets usage limits. The
client's bot is isolated from other tenants' data.

**Why this priority**: Multi-tenancy is the SaaS business model. Without client
isolation, the product cannot be sold to multiple organizations.

**Independent Test**: Can be tested by creating two client accounts with separate
knowledge bases and verifying that a query answered for Client A does not surface
data belonging to Client B.

**Acceptance Scenarios**:

1. **Given** an operator is in the admin dashboard, **When** they create a new client
   with a name, plan, and channel config, **Then** a new isolated tenant environment is
   provisioned and the bot responds only to that client's registered channels.
2. **Given** a client reaches their monthly message quota, **When** a user sends a
   message, **Then** the bot notifies the user that the service limit has been reached.
3. **Given** an admin deletes a client, **When** confirmed, **Then** all associated
   conversations, documents, and settings are permanently removed.

---

### User Story 5 — Investor Uses the Bot on WhatsApp (Priority: P5)

An investor messages the PSX bot through WhatsApp (via a registered Twilio number) and
receives the same question-answering experience as on Telegram.

**Why this priority**: WhatsApp has significantly higher penetration in Pakistan than
Telegram. Reaching WhatsApp users is critical for market adoption but is architecturally
parallel to Telegram support.

**Independent Test**: Can be tested by sending a question to the WhatsApp number linked
to a client and verifying the bot response matches the expected RAG output.

**Acceptance Scenarios**:

1. **Given** a WhatsApp number is configured for a client, **When** a user sends a text
   or voice message, **Then** the bot responds correctly via WhatsApp within 15 seconds.
2. **Given** the Twilio webhook is unreachable, **When** a WhatsApp message arrives,
   **Then** the system queues the message and retries delivery on recovery.

---

### Edge Cases

- When the LLM service is offline: system returns an immediate friendly error message to the user; the message is not queued or retried.
- What happens if a document upload exceeds the maximum allowed file size?
- How does the system handle simultaneous high-volume messages from multiple tenants?
- What if a Telegram or WhatsApp API token is revoked mid-session?
- How are conversations handled when a user switches between WhatsApp and Telegram?
- What happens when the vector search returns zero results for a query?
- How does the system handle duplicate or near-identical uploaded documents?
- What if audio transcription fails partway through a long voice message?

---

## Requirements *(mandatory)*

### Functional Requirements

#### Bot Interaction

- **FR-001**: System MUST accept text messages from registered Telegram bots and return
  natural-language answers grounded in the tenant's PSX knowledge base.
- **FR-002**: System MUST accept text messages via WhatsApp (Twilio) and return
  natural-language answers grounded in the tenant's PSX knowledge base.
- **FR-003**: System MUST transcribe voice/audio messages and process them through the
  same RAG pipeline as text queries.
- **FR-004**: System MUST respond with a graceful fallback message when no relevant
  context is found in the knowledge base.
- **FR-004b**: System MUST return an immediate, user-friendly error message when the
  LLM service is unavailable; messages MUST NOT be queued or retried automatically.
- **FR-005**: System MUST maintain per-user conversation history to support follow-up
  questions within a session. A session expires after 30 minutes of inactivity; a new
  message after the timeout begins a fresh conversation.
- **FR-006**: System MUST enforce per-tenant message quotas and notify users when limits
  are reached.
- **FR-007**: System MUST reject and notify users for unsupported message types (e.g.,
  stickers, location shares).

#### RAG & Knowledge Base

- **FR-008**: System MUST support ingestion of PDF and plain-text documents into a
  per-tenant vector knowledge base.
- **FR-009**: System MUST chunk, embed, and index documents so they are searchable by
  semantic similarity.
- **FR-010**: System MUST retrieve the most relevant document chunks for each user query
  before generating a response.
- **FR-011**: System MUST support deletion and re-ingestion of documents to keep the
  knowledge base current.
- **FR-012**: System MUST deduplicate documents on re-upload to prevent duplicate results.
- **FR-013**: System MUST report document ingestion status (pending, processing, ready,
  failed) in the admin dashboard.

#### Admin Dashboard

- **FR-014**: System MUST provide a web-based admin dashboard protected by authenticated
  login.
- **FR-015**: Admin MUST be able to create, edit, and delete client (tenant) accounts.
- **FR-016**: Admin MUST be able to upload, view, and delete knowledge base documents
  per client.
- **FR-017**: Admin MUST be able to configure bot channel credentials (Telegram token,
  WhatsApp number) per client.
- **FR-018**: Dashboard MUST display usage metrics (message count, active users, query
  volume) per client.
- **FR-019**: Admin MUST be able to set and modify message quota limits per client plan.

#### Multi-Tenancy & Security

- **FR-020**: System MUST isolate each tenant's knowledge base, conversations, and
  settings so no data leaks across tenants.
- **FR-021**: System MUST authenticate admin dashboard users with secure credentials
  (email + password minimum).
- **FR-022**: System MUST store all secrets (API keys, tokens, credentials) in
  environment configuration and never expose them in responses or logs.
- **FR-023**: System MUST rate-limit incoming bot messages to 60 messages/minute per
  tenant by default; the limit MUST be configurable per subscription plan.
- **FR-024**: System MUST log all admin actions (document upload, client creation,
  config changes) for audit purposes.

### Key Entities

- **Tenant (Client)**: An organization using the SaaS. Has a name, subscription plan,
  bot channel configs, document collection, and usage counters.
- **BotUser**: An end-user interacting via Telegram or WhatsApp. Identity is
  platform-specific (a Telegram user and a WhatsApp user are always separate BotUsers,
  even if the same person). Has independent conversation history and quota per platform.
  Belongs to a tenant.
- **Conversation**: A session-scoped exchange between a bot user and the bot. Contains
  an ordered list of messages. A session expires after 30 minutes of inactivity; the
  next message from the user starts a new conversation.
- **Message**: A single turn in a conversation. Has a role (user/bot), content type
  (text/audio), raw content, and optional transcription.
- **Document**: A file uploaded to a tenant's knowledge base. Has metadata (name,
  upload date, processing status) and is processed into searchable chunks.
- **DocumentChunk**: A semantic segment of a document with an embedding vector,
  used for retrieval during query processing.
- **AdminUser**: An operator with access to the admin dashboard. Has credentials and role.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive a relevant, grounded bot response within 10 seconds for 95%
  of text queries under normal load.
- **SC-002**: Voice messages are transcribed and answered within 20 seconds for
  recordings up to 3 minutes long.
- **SC-003**: Document ingestion completes and content becomes queryable within 5 minutes
  of upload for files up to 50 MB.
- **SC-004**: System supports at least 10 concurrent tenants with full data isolation,
  verified by cross-tenant query tests returning zero cross-contamination results.
- **SC-005**: Admin can onboard a new client (create account, configure channels, upload
  documents) in under 15 minutes without developer assistance.
- **SC-006**: System sustains 500 messages per minute across all tenants without
  degraded response times.
- **SC-007**: Bot correctly refuses out-of-scope queries (non-PSX topics) in 90%+ of
  structured test cases.
- **SC-008**: Zero tenant data leakage across 100 targeted cross-tenant query tests.
- **SC-009**: System achieves 99.5% monthly uptime (≤3.6 hours unplanned downtime per
  month), measured by external health monitoring.

---

## Assumptions

- PSX data is provided through uploaded documents (PDFs, text files); live market feed
  integration is out of scope for Phase 1.
- The local LLM is self-hosted on the deployment infrastructure; no per-inference API
  costs are assumed.
- WhatsApp integration uses Twilio's WhatsApp Business API; Twilio sandbox is acceptable
  for development and testing.
- Admin users are internal operators; a self-service client signup flow is out of scope
  for Phase 1.
- The system targets the Pakistani market; primary language support is English with Urdu
  as a secondary consideration for voice transcription.
- Voice transcription accuracy targets assume reasonably clear audio in English or Urdu.
- Deployment targets Docker/Docker Compose for development and AWS (ECS or Kubernetes)
  for production.

---

## Out of Scope

- Live/real-time PSX market data feed integration (Phase 1 uses uploaded documents only).
- Mobile or native app for end-users (bot channels only: Telegram, WhatsApp).
- Self-service client registration or billing/payment processing.
- Support for messaging channels beyond Telegram and WhatsApp.
- Multi-language UI for the admin dashboard (English only, Phase 1).
- Social authentication (OAuth2/SSO login) for admin users.

---

## Clarifications

### Session 2026-04-07

- Q: When does a conversation session expire? → A: 30-minute inactivity timeout; next message starts a new session.
- Q: If the same person uses both WhatsApp and Telegram, are they one BotUser or two? → A: Two independent users — platform-specific identity, separate history and quota per platform.
- Q: When the LLM service is offline, what does the system do? → A: Return an immediate friendly error to the user; message is not queued or retried.
- Q: What is the uptime/availability SLA? → A: 99.5% monthly uptime (~3.6 hrs downtime/month); single-AZ with health monitoring.
- Q: What is the per-tenant rate limit for incoming bot messages? → A: 60 messages/minute per tenant (configurable per plan).

---

## Dependencies

- **Telegram Bot API**: Required for Telegram channel integration. Depends on valid bot
  tokens provisioned via BotFather.
- **Twilio WhatsApp API**: Required for WhatsApp channel. Depends on an approved Twilio
  account with a WhatsApp-enabled number.
- **OpenAI Whisper API**: Required for voice transcription. Depends on a valid OpenAI
  API key.
- **Local LLM (Ollama)**: Required for response generation. Depends on a running
  instance with a suitable model available (e.g., Llama 3, Mistral).
- **MongoDB Atlas**: Required for persistent storage. Free tier acceptable for
  development.
- **Docker / Docker Compose**: Required for local development environment orchestration.
- **AWS** (ECS or Kubernetes): Required for production deployment.
