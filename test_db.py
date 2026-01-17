"""Test database connection"""
import asyncio

from sqlalchemy import select, text

from app.infrastructure.database import create_engine, get_session_factory
from app.infrastructure.models import User


async def test():
    # Test raw connection
    engine = create_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print(f"Raw connection: {result.scalar()}")

    # Test with session and User model
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == "demo"))
        user = result.scalars().first()
        print(f"User lookup by id='demo': {user}")

        # Try by email
        result2 = await session.execute(select(User).where(User.email == "demo@demo.com"))
        user2 = result2.scalars().first()
        print(f"User lookup by email: {user2}")
        if user2:
            print(f"  ID: {user2.id}, Balance: {user2.credit_balance}")

asyncio.run(test())
