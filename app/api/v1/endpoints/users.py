"""User management endpoints."""


from fastapi import APIRouter, HTTPException

from app.api.deps import PaymentDep, UserDep
from app.schemas.user import CreditPurchase, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    user: UserDep,
) -> UserResponse:
    """Get current user profile and credit balance."""
    return user


@router.post("/credits/buy", response_model=UserResponse)
async def buy_credits(
    purchase: CreditPurchase,
    user: UserDep,
    payment_service: PaymentDep,
) -> UserResponse:
    """Buy credits (Simulated Payment).
    
    Price must be:
    - 19€ for 1 credit
    - 49€ for 3 credits
    - 99€ for 10 credits
    """
    # Simple validation logic for MVP
    valid_packs = {
        1: 19.0,
        3: 49.0,
        10: 99.0
    }

    expected_price = valid_packs.get(purchase.amount)
    if not expected_price or purchase.price != expected_price:
        raise HTTPException(
            status_code=400,
            detail="Invalid pack configuration. Available: 1@19€, 3@49€, 10@99€"
        )

    await payment_service.buy_credits(user.id, purchase.amount, purchase.price)

    # Refresh user
    # Note: In a real app we'd reload from DB,
    # but payment_service updates the balance on the same object or we can assume success
    user.credit_balance += purchase.amount

    return user
