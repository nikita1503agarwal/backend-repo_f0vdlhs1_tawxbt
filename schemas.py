"""
Database Schemas for School Mini-Market POS

Each Pydantic model maps to a MongoDB collection whose name is the lowercase of the class name.
Use these models to validate incoming data and to keep a consistent structure in the DB.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class Product(BaseModel):
    """
    Products available in the school mini-market
    Collection: "product"
    """
    name: str = Field(..., description="Product name")
    sku: str = Field(..., description="Stock keeping unit (unique code)")
    price: float = Field(..., ge=0, description="Unit price")
    stock: int = Field(0, ge=0, description="Units in stock")
    category: Optional[str] = Field(None, description="Category e.g. snacks, drinks")
    barcode: Optional[str] = Field(None, description="Barcode if available")
    active: bool = Field(True, description="Whether product is available for sale")


class Student(BaseModel):
    """
    Students who buy from the mini-market (optional, can sell to guests)
    Collection: "student"
    """
    name: str = Field(...)
    class_name: Optional[str] = Field(None, description="Class or grade, e.g. 7A")
    student_id: Optional[str] = Field(None, description="School-provided ID")


class SaleItem(BaseModel):
    """
    Line item within a sale transaction (embedded in Sale)
    Not a collection by itself.
    """
    product_id: str = Field(..., description="Mongo ObjectId as string")
    name: str
    sku: str
    price: float = Field(..., ge=0)
    quantity: int = Field(..., ge=1)
    subtotal: float = Field(..., ge=0)


class Sale(BaseModel):
    """
    Sale transactions
    Collection: "sale"
    """
    items: List[SaleItem]
    total: float = Field(..., ge=0)
    paid: float = Field(..., ge=0)
    change: float = Field(..., ge=0)
    customer_name: Optional[str] = Field(None)
    student_ref: Optional[str] = Field(None, description="Linked student _id as string, if any")
    payment_method: str = Field("cash", description="cash | card | other")
