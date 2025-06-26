import os
from dotenv import load_dotenv
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Load .env
load_dotenv()

# Async engine with asyncpg
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(
   DATABASE_URL,
   echo=True,
   connect_args={"check_same_thread": False}  # needed for SQLite + async
)
# Async session factory
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Initialize DB (to call on startup)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

# Dependency for endpoints
async def get_session():
    async with async_session() as session:
        yield session
