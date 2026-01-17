"""User Repository."""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import CreditTransaction, User


class UserRepository:
    """Repository for User and Credit management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def create_user(self, email: str, initial_credits: int = 5) -> User:
        """Create new user."""
        user = User(email=email, credit_balance=initial_credits)
        self.session.add(user)
        # Flush to get user.id before logging transaction
        await self.session.flush()
        # Add initial transaction log
        await self.log_transaction(user, initial_credits, "Welcome bonus")
        return user

    async def update_balance(self, user_id: str, amount: int, description: str) -> int:
        """Update user credit balance.
        
        Args:
            user_id: User ID
            amount: Amount to add (positive) or remove (negative)
            description: Reason for update
            
        Returns:
            New balance
        
        Raises:
            ValueError: If insufficient funds
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if user.credit_balance + amount < 0:
            raise ValueError("Insufficient credits")

        user.credit_balance += amount

        # Log transaction
        log = CreditTransaction(
            user_id=user_id,
            amount=amount,
            description=description
        )
        self.session.add(log)

        return user.credit_balance

    async def log_transaction(self, user: User, amount: int, description: str) -> None:
        """Log a credit transaction."""
        log = CreditTransaction(
            user_id=user.id,
            amount=amount,
            description=description
        )
        self.session.add(log)
