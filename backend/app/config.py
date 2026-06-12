from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://localhost/psx_chatbot"

    # JWT
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 480

    # OpenAI
    openai_api_key: str = ""

    # LLM Provider (ollama, gemini, openai)
    llm_provider: str = "gemini"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Embeddings
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # FAISS
    faiss_index_dir: str = "./indexes"

    # RAG: maximum L2 distance for a chunk to count as "relevant".
    # paraphrase-multilingual-MiniLM-L12-v2 vectors are normalised, so L2
    # distance ranges 0..2 (0 = identical, 2 = opposite). 1.2 ≈ cosine sim 0.28.
    # Lower = stricter grounding. Tune per knowledge base.
    rag_max_distance: float = 1.2

    # Encryption key for channel secrets (Fernet).
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = ""

    # Seed admin
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "change-me"

    # CORS
    frontend_url: str = "http://localhost:5173"

    # Environment
    environment: str = "development"
    disable_docs: bool = False


settings = Settings()
