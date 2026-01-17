"""User schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Shared user properties."""
    email: EmailStr


class UserCreate(UserBase):
    """Properties to receive on user creation."""
    pass


class UserResponse(UserBase):
    """Properties to return to client."""
    id: str
    credit_balance: int

    model_config = ConfigDict(from_attributes=True)


class CreditPurchase(BaseModel):
    """Purchase request."""
    amount: int
    price: float
