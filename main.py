import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Student, Sale, SaleItem

app = FastAPI(title="School Mini-Market POS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "School Mini-Market POS API running"}


# Product Endpoints
@app.post("/api/products")
def create_product(product: Product):
    # Ensure SKU uniqueness
    existing = list(db["product"].find({"sku": product.sku})) if db else []
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    _id = create_document("product", product)
    return {"_id": _id}


@app.get("/api/products")
def list_products(q: Optional[str] = None):
    filter_dict = {"active": True}
    if q:
        filter_dict["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
            {"barcode": {"$regex": q, "$options": "i"}},
        ]
    items = get_documents("product", filter_dict)
    # Convert ObjectId to string
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
    return items


class StockUpdate(BaseModel):
    delta: int


@app.post("/api/products/{product_id}/stock")
def update_stock(product_id: str, payload: StockUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    res = db["product"].update_one({"_id": oid}, {"$inc": {"stock": payload.delta}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    prod = db["product"].find_one({"_id": oid})
    prod["_id"] = str(prod["_id"])  # type: ignore
    return prod


# Students (optional)
@app.post("/api/students")
def create_student(student: Student):
    _id = create_document("student", student)
    return {"_id": _id}


@app.get("/api/students")
def list_students(q: Optional[str] = None):
    filter_dict = {}
    if q:
        filter_dict["name"] = {"$regex": q, "$options": "i"}
    items = get_documents("student", filter_dict)
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
    return items


# Sales
class SaleRequest(BaseModel):
    items: List[dict]
    paid: float
    customer_name: Optional[str] = None
    student_ref: Optional[str] = None
    payment_method: str = "cash"


@app.post("/api/sales")
def create_sale(request: SaleRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Fetch products and compute totals, validate stock
    items: List[SaleItem] = []
    total = 0.0
    for line in request.items:
        pid = line.get("product_id")
        qty = int(line.get("quantity", 1))
        try:
            oid = ObjectId(pid)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid product id: {pid}")
        prod = db["product"].find_one({"_id": oid, "active": True})
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found or inactive")
        if int(prod.get("stock", 0)) < qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod.get('name')}")
        price = float(prod.get("price", 0))
        subtotal = round(price * qty, 2)
        total += subtotal
        items.append(SaleItem(
            product_id=str(prod["_id"]),
            name=prod.get("name"),
            sku=prod.get("sku"),
            price=price,
            quantity=qty,
            subtotal=subtotal
        ))

    total = round(total, 2)
    if request.paid < total:
        raise HTTPException(status_code=400, detail="Paid amount is less than total")
    change = round(request.paid - total, 2)

    # Create sale record
    sale = Sale(
        items=items,
        total=total,
        paid=request.paid,
        change=change,
        customer_name=request.customer_name,
        student_ref=request.student_ref,
        payment_method=request.payment_method,
    )
    sale_id = create_document("sale", sale)

    # Deduct stock
    for it in items:
        db["product"].update_one({"_id": ObjectId(it.product_id)}, {"$inc": {"stock": -it.quantity}})

    return {"_id": sale_id, "total": total, "paid": request.paid, "change": change}


@app.get("/api/sales")
def list_sales(limit: int = 50):
    items = get_documents("sale", {}, limit=limit)
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
        for li in it.get("items", []):
            # ensure nested is serializable
            if isinstance(li.get("product_id"), ObjectId):
                li["product_id"] = str(li["product_id"])  # type: ignore
    return items


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
