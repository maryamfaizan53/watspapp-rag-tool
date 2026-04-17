from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
from urllib.parse import urlparse, urlunparse

# Parse database URL and handle SSL for asyncpg
database_url = settings.database_url

# Strip params asyncpg doesn't understand (sslmode, channel_binding)
# and normalise to ssl=require for Neon
_unsupported = ('sslmode', 'channel_binding')
if any(p in database_url for p in _unsupported):
    parsed = urlparse(database_url)
    query_params = [
        p for p in parsed.query.split('&')
        if p and not any(p.startswith(u) for u in _unsupported)
    ]
    new_query = '&'.join(query_params)
    database_url = urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment,
    ))

# Ensure ssl=require is present for Neon
if 'neon.tech' in database_url and 'ssl=' not in database_url:
    sep = '&' if '?' in database_url else '?'
    database_url += f'{sep}ssl=require'

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
