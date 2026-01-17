"""Payment Service."""

import logging

from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for handling payments and credit purchases."""

    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def buy_credits(self, user_id: str, amount: int, price: float) -> int:
        """Process purchase of credits.
        
        Args:
            user_id: User ID
            amount: Number of credits
            price: Price paid (validation only for MVP)
            
        Returns:
            New balance
        """
        # Mock Stripe payment processing
        logger.info(f"Processing payment of {price}€ for {amount} credits (User: {user_id})")

        # In a real app, we would verify Stripe intent here

        # Add credits
        new_balance = await self.user_repo.update_balance(
            user_id=user_id,
            amount=amount,
            description=f"Purchase: {amount} credits for {price}€"
        )

        return new_balance
