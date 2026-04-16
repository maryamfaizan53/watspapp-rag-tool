from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
from urllib.parse import urlparse, urlunparse

# Parse database URL and handle SSL for asyncpg
database_url = settings.database_url

# If URL has sslmode parameter, convert it for asyncpg compatibility
if 'sslmode' in database_url:
    # Parse the URL
    parsed = urlparse(database_url)
    # Remove sslmode from query
    query_params = parsed.query.split('&')
    query_params = [p for p in query_params if not p.startswith('sslmode')]
    new_query = '&'.join(query_params)
    # Rebuild URL without sslmode
    database_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    # Add ssl parameter for asyncpg
    if 'neon.tech' in database_url:
        database_url += '?ssl=require'

# Create async engine
engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def connect_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


async def get_db() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session
