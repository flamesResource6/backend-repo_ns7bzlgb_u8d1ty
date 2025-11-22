"""
Database Schemas for Shopearn Pro

Each Pydantic model corresponds to a MongoDB collection. The collection name is the lowercase of the class name.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

class User(BaseModel):
    role: str = Field(..., description="buyer | affiliate | admin")
    name: str
    email: str
    password_hash: str
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    is_active: bool = True
    ad_free: bool = False
    subscription_expiry: Optional[datetime] = None

class Product(BaseModel):
    affiliate_id: str = Field(..., description="Owner affiliate user id")
    images: List[str] = Field(default_factory=list)
    title: str
    description: Optional[str] = None
    price: float
    vendor: str = Field(..., description="amazon|flipkart|meesho|shopify|myntra|ajio|alibaba|snapdeal")
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    hot_deal: bool = False
    hot_deal_expiry: Optional[datetime] = None
    featured: bool = False
    clicks: int = 0
    orders: int = 0
    affiliate_link: Optional[str] = None

class Order(BaseModel):
    user_id: str
    product_id: str
    affiliate_id: str
    status: str = Field(default="Redirected")
    vendor_url: Optional[str] = None

class Click(BaseModel):
    type: str = Field(..., description="logo|product")
    user_id: Optional[str] = None
    product_id: Optional[str] = None
    affiliate_id: Optional[str] = None
    ip: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class AdminSettings(BaseModel):
    links: Dict[str, str] = Field(default_factory=dict, description="platform -> affiliate url")

class AdminAuditLog(BaseModel):
    admin_id: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
