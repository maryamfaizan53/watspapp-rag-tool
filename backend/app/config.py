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

    # LLM Provider (ollama, gemini)
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

    # Encryption key for channel secrets (Fernet)
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
