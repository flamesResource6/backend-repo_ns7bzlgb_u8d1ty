import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document
from schemas import User as UserSchema, Product as ProductSchema, Order as OrderSchema, Click as ClickSchema, AdminSettings as AdminSettingsSchema, AdminAuditLog as AdminAuditLogSchema

app = FastAPI(title="Shopearn Pro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SignupRequest(BaseModel):
    role: str = Field(..., description="buyer|affiliate|admin")
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class ProductCreateRequest(BaseModel):
    images: List[str] = Field(default_factory=list)
    title: str
    description: Optional[str] = None
    price: float
    vendor: str
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    rating: Optional[float] = None
    affiliate_link: Optional[str] = None
    hot_deal: bool = False
    hot_deal_expiry: Optional[datetime] = None

class ProductUpdateRequest(BaseModel):
    images: Optional[List[str]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    vendor: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    rating: Optional[float] = None
    affiliate_link: Optional[str] = None
    hot_deal: Optional[bool] = None
    hot_deal_expiry: Optional[datetime] = None
    featured: Optional[bool] = None

class SearchQuery(BaseModel):
    q: Optional[str] = None
    category: Optional[str] = None

class AdminLinks(BaseModel):
    links: Dict[str, str]


@app.get("/")
def root():
    return {"name": "Shopearn Pro API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:120]}"
    return response


# Simple password hashing (NOT for production). In real app, use Firebase/Auth providers
import hashlib

def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


# Auth Endpoints
@app.post("/auth/signup")
def signup(req: SignupRequest):
    existing = db["user"].find_one({"email": req.email}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="Account exists — please login instead.")
    user = UserSchema(
        role=req.role,
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        phone=req.phone,
        age=req.age,
        gender=req.gender,
    )
    user_id = create_document("user", user)
    return {"ok": True, "user_id": user_id}


@app.post("/auth/login")
def login(req: LoginRequest):
    u = db["user"].find_one({"email": req.email}) if db else None
    if not u or u.get("password_hash") != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    u["_id"] = str(u["_id"]) if "_id" in u else None
    return {"ok": True, "user": u}


# Products
@app.post("/affiliate/products")
def create_product(req: ProductCreateRequest, user_id: str):
    aff = db["user"].find_one({"_id": ObjectId(user_id)}) if db else None
    if not aff or aff.get("role") != "affiliate":
        raise HTTPException(status_code=403, detail="Only affiliates can upload")
    prod = ProductSchema(
        affiliate_id=user_id,
        images=req.images,
        title=req.title,
        description=req.description,
        price=req.price,
        vendor=req.vendor,
        category=req.category,
        tags=req.tags or [],
        rating=req.rating,
        hot_deal=req.hot_deal,
        hot_deal_expiry=req.hot_deal_expiry,
        affiliate_link=req.affiliate_link,
    )
    pid = create_document("product", prod)
    return {"ok": True, "product_id": pid}


@app.get("/affiliate/my-products")
def my_products(user_id: str):
    items = list(db["product"].find({"affiliate_id": user_id}).sort("updated_at", -1)) if db else []
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
    return {"ok": True, "items": items}


@app.get("/products")
def list_products(q: Optional[str] = None, category: Optional[str] = None, hot: Optional[bool] = None, limit: int = 50):
    filt: Dict[str, Any] = {}
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    if category:
        filt["category"] = category
    if hot is not None:
        filt["hot_deal"] = hot
    items = list(db["product"].find(filt).limit(int(limit))) if db else []
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
    return {"ok": True, "items": items}


@app.get("/products/{product_id}")
def get_product(product_id: str):
    doc = db["product"].find_one({"_id": ObjectId(product_id)}) if db else None
    if not doc:
        raise HTTPException(404, detail="Not found")
    doc["_id"] = str(doc["_id"])
    return {"ok": True, "item": doc}


@app.patch("/affiliate/products/{product_id}")
def update_product(product_id: str, req: ProductUpdateRequest, user_id: str):
    prod = db["product"].find_one({"_id": ObjectId(product_id)}) if db else None
    if not prod:
        raise HTTPException(404, detail="Not found")
    if prod.get("affiliate_id") != user_id:
        raise HTTPException(403, detail="Not owner")
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    updates["updated_at"] = datetime.now(timezone.utc)
    db["product"].update_one({"_id": ObjectId(product_id)}, {"$set": updates})
    return {"ok": True}


# Admin settings: platform links
@app.get("/admin/links")
def get_links():
    doc = db["adminsettings"].find_one({}) if db else None
    if not doc:
        return {"ok": True, "links": {}}
    return {"ok": True, "links": doc.get("links", {})}


@app.post("/admin/links")
def set_links(payload: AdminLinks, admin_email: Optional[str] = None, admin_password: Optional[str] = None):
    if not (admin_email == "shekharxlr8@gmail.com" and admin_password == "Shekhar_4t7"):
        raise HTTPException(401, detail="Invalid admin credentials")
    coll = db["adminsettings"]
    existing = coll.find_one({})
    if existing:
        coll.update_one({"_id": existing["_id"]}, {"$set": {"links": payload.links, "updated_at": datetime.now(timezone.utc)}})
    else:
        create_document("adminsettings", AdminSettingsSchema(links=payload.links))
    try:
        create_document("adminauditlog", AdminAuditLogSchema(admin_id="hardcoded-admin", action="update_links", details=payload.links))
    except Exception:
        pass
    return {"ok": True}


@app.get("/admin/stats")
def admin_stats(admin_email: Optional[str] = None, admin_password: Optional[str] = None):
    if not (admin_email == "shekharxlr8@gmail.com" and admin_password == "Shekhar_4t7"):
        raise HTTPException(401, detail="Invalid admin credentials")
    users = db["user"].count_documents({}) if db else 0
    affiliates = db["user"].count_documents({"role": "affiliate"}) if db else 0
    buyers = db["user"].count_documents({"role": "buyer"}) if db else 0
    subscribers = db["user"].count_documents({"ad_free": True}) if db else 0
    products = db["product"].count_documents({}) if db else 0
    orders = db["order"].count_documents({}) if db else 0
    return {"ok": True, "stats": {"users": users, "buyers": buyers, "affiliates": affiliates, "subscribers": subscribers, "products": products, "orders": orders}}


# Redirect endpoints for tracking
@app.get("/r/{platform}")
def redirect_platform(platform: str, request: Request, user_id: Optional[str] = None):
    doc = db["adminsettings"].find_one({}) if db else None
    url = (doc or {}).get("links", {}).get(platform.lower())
    if not url:
        raise HTTPException(404, detail="Link not available yet.")
    ip = request.client.host if request.client else None
    try:
        create_document("click", ClickSchema(type="logo", user_id=user_id, product_id=None, affiliate_id=None, ip=ip, meta={"platform": platform}))
    except Exception:
        pass
    return RedirectResponse(url)


@app.get("/r/product/{product_id}")
def redirect_product(product_id: str, request: Request, user_id: Optional[str] = None):
    prod = db["product"].find_one({"_id": ObjectId(product_id)}) if db else None
    if not prod or not prod.get("affiliate_link"):
        raise HTTPException(404, detail="Affiliate link not available")
    try:
        db["product"].update_one({"_id": ObjectId(product_id)}, {"$inc": {"clicks": 1}})
    except Exception:
        pass
    ip = request.client.host if request.client else None
    try:
        create_document("click", ClickSchema(type="product", user_id=user_id, product_id=product_id, affiliate_id=prod.get("affiliate_id"), ip=ip, meta={}))
    except Exception:
        pass
    return RedirectResponse(prod["affiliate_link"])


# Orders - created on checkout redirect (for visibility only)
@app.post("/orders")
def create_order(product_id: str, user_id: Optional[str] = None):
    prod = db["product"].find_one({"_id": ObjectId(product_id)}) if db else None
    if not prod:
        raise HTTPException(404, detail="Product not found")
    order = OrderSchema(user_id=user_id or "guest", product_id=product_id, affiliate_id=prod.get("affiliate_id"), status="Redirected", vendor_url=prod.get("affiliate_link"))
    oid = create_document("order", order)
    return {"ok": True, "order_id": oid}


@app.get("/orders")
def list_orders(user_id: Optional[str] = None):
    filt = {}
    if user_id:
        filt["user_id"] = user_id
    items = list(db["order"].find(filt).sort("created_at", -1)) if db else []
    for it in items:
        it["_id"] = str(it["_id"]) if "_id" in it else None
    return {"ok": True, "items": items}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
