"""
models/schemas.py
-----------------
Pydantic v2 request / response schemas for all OLTP entities.
Kept in one file for simplicity; split per-entity as the project grows.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ===========================================================================
# Address
# ===========================================================================
class AddressBase(BaseModel):
    type: str = Field(..., examples=["home"], description="home | work | restaurant | other")
    house_number: str
    street: str
    locality: str
    city: str
    pincode: str = Field(..., max_length=6)


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    type: Optional[str] = None
    house_number: Optional[str] = None
    street: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None


class AddressResponse(AddressBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Customer
# ===========================================================================
class CustomerBase(BaseModel):
    address_id: int
    name: str
    mobile_number: str = Field(..., max_length=15)
    email: Optional[str] = None
    status: str = Field(default="active", description="active | inactive | blocked")


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    address_id: Optional[int] = None
    name: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Restaurant
# ===========================================================================
class RestaurantBase(BaseModel):
    address_id: int
    name: str
    mobile_number: str = Field(..., max_length=15)
    status: str = Field(default="active", description="active | inactive | suspended")


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(BaseModel):
    address_id: Optional[int] = None
    name: Optional[str] = None
    mobile_number: Optional[str] = None
    status: Optional[str] = None


class RestaurantResponse(RestaurantBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Delivery Partner
# ===========================================================================
class DeliveryPartnerBase(BaseModel):
    address_id: int
    name: str
    mobile_number: str = Field(..., max_length=15)
    status: str = Field(
        default="available",
        description="available | on_trip | offline | suspended"
    )


class DeliveryPartnerCreate(DeliveryPartnerBase):
    pass


class DeliveryPartnerUpdate(BaseModel):
    address_id: Optional[int] = None
    name: Optional[str] = None
    mobile_number: Optional[str] = None
    status: Optional[str] = None


class DeliveryPartnerResponse(DeliveryPartnerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Item
# ===========================================================================
class ItemBase(BaseModel):
    restaurant_id: int
    name: str
    price: Decimal = Field(..., gt=0, decimal_places=2)
    is_available: bool = True


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = None
    is_available: Optional[bool] = None


class ItemResponse(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Order
# ===========================================================================
class OrderBase(BaseModel):
    customer_id: int
    restaurant_id: int
    delivery_address_id: int
    total_amount: Decimal = Field(..., gt=0, decimal_places=2)


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    delivery_partner_id: Optional[int] = None
    status: Optional[str] = Field(
        default=None,
        description="created | confirmed | preparing | out_for_delivery | delivered | cancelled"
    )
    total_amount: Optional[Decimal] = None


class OrderResponse(OrderBase):
    order_id: int
    delivery_partner_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Order Item
# ===========================================================================
class OrderItemBase(BaseModel):
    order_id: int
    item_id: int
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0, decimal_places=2)


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(OrderItemBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# Order Event
# ===========================================================================
class OrderEventCreate(BaseModel):
    order_id: int
    event_type: str = Field(
        ...,
        description="created | confirmed | preparing | out_for_delivery | delivered | cancelled"
    )
    triggered_by: Optional[str] = Field(
        default=None,
        description="system | customer | restaurant | delivery_partner"
    )
    notes: Optional[str] = None


class OrderEventResponse(OrderEventCreate):
    id: int
    event_timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}