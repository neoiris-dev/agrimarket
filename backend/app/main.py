"""AgriMarket - API REST (FastAPI + PostgreSQL). Cubre HU-01..HU-13 del MVP."""
import os, re, unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import quote

import bcrypt, jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String,
                        Text, create_engine, func, or_, text)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

SECRET = os.environ["SECRET_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session_ = sessionmaker(engine)
Base = declarative_base()
UNITS = "kg|lb|bulto|canastilla|unidad"
PAGE = 20
MAX_IMG = 680_000  # ~500 KB en base64 (RNF-04)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, index=True, nullable=False)
    phone = Column(String(10), unique=True, nullable=False)
    pw = Column(String(80), nullable=False)
    role = Column(String(10), nullable=False)  # producer | consumer | admin
    farm = Column(String(120))
    municipality = Column(String(60))
    active = Column(Boolean, default=True)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(60), unique=True, nullable=False)
    active = Column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    producer_id = Column(ForeignKey("users.id"), nullable=False)
    category_id = Column(ForeignKey("categories.id"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    unit = Column(String(12), nullable=False)
    stock = Column(Float, nullable=False)
    image = Column(Text)
    visible = Column(Boolean, default=True)
    producer = relationship(User)
    category = relationship(Category)


class Req(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True)
    consumer_id = Column(ForeignKey("users.id"), nullable=False)
    product_id = Column(ForeignKey("products.id"), nullable=False)
    qty = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    address = Column(String(200), nullable=False)
    status = Column(String(10), default="pending")  # pending|accepted|rejected|delivered
    reason = Column(String(200))
    total = Column(Float)
    created = Column(DateTime, default=datetime.utcnow)
    consumer = relationship(User)
    product = relationship(Product)


def hash_(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    return cleaned.lower()


@asynccontextmanager
async def lifespan(_):
    if engine.dialect.name == "postgresql":
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    Base.metadata.create_all(engine)
    with Session_() as s:
        if not s.query(User).filter_by(role="admin").first():
            s.add(User(name="Administrador", email="admin@agrimarket.co", phone="3000000000",
                       pw=hash_(os.getenv("ADMIN_PASSWORD", "Admin2026*")), role="admin"))
            s.add_all(Category(name=n) for n in ["Frutas", "Verduras", "Tubérculos", "Hierbas", "Lácteos artesanales"])
            s.commit()
    yield


app = FastAPI(title="AgriMarket API", version="1.0.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def db():
    with Session_() as s:
        yield s


def current(c: Optional[HTTPAuthorizationCredentials] = Depends(bearer), s: Session = Depends(db)):
    if c is None or not c.credentials:
        raise HTTPException(401, "Sesión inválida o vencida")
    try:
        payload = jwt.decode(c.credentials, SECRET, algorithms=["HS256"])
        u = s.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(401, "Sesión inválida o vencida")
    if not u or not u.active:
        raise HTTPException(403, "Tu cuenta está suspendida")
    return u


def need(*roles):
    def dep(u: User = Depends(current)):
        if u.role not in roles:
            raise HTTPException(403, "No tienes permiso para esta acción")
        return u
    return dep


def session(u):
    tok = jwt.encode({"sub": str(u.id), "exp": datetime.utcnow() + timedelta(hours=12)}, SECRET, "HS256")
    return {"token": tok, "user": {"id": u.id, "name": u.name, "role": u.role}}


class Reg(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(pattern=r"^\d{10}$")
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(pattern="^(producer|consumer)$")
    farm: Optional[str] = Field(None, max_length=120)
    municipality: Optional[str] = None
    consent: bool


class Login(BaseModel):
    email: EmailStr
    password: str


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category_id: int
    description: Optional[str] = None
    price: float = Field(gt=0)
    unit: str = Field(pattern=f"^({UNITS})$")
    stock: float = Field(gt=0)
    image: Optional[str] = None


class ReqIn(BaseModel):
    product_id: int
    quantity: float = Field(gt=0)
    date: date
    address: str = Field(min_length=3, max_length=200)


class ReqUp(BaseModel):
    status: str = Field(pattern="^(accepted|rejected|delivered)$")
    reason: Optional[str] = Field(None, max_length=200)


def pj(p):
    return dict(id=p.id, name=p.name, description=p.description, price=p.price, unit=p.unit, stock=p.stock,
                image=p.image, visible=p.visible, category=p.category.name, category_id=p.category_id,
                farm=p.producer.farm, municipality=p.producer.municipality, producer=p.producer.name)


def rj(r, wa=False, phone=False):
    d = dict(id=r.id, product=r.product.name, unit=r.product.unit, quantity=r.qty, date=str(r.date),
             address=r.address, status=r.status, reason=r.reason, total=r.total, consumer=r.consumer.name)
    if phone:
        d["phone"] = r.consumer.phone
    if wa and r.status in ("accepted", "delivered"):
        msg = f"Hola, soy {r.consumer.name}. Solicitud #{r.id}: {r.qty:g} {r.product.unit} de {r.product.name}."
        d["wa"] = f"https://wa.me/57{r.product.producer.phone}?text={quote(msg)}"
    return d


@app.get("/api/health")
def health(): return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(b: Reg, s: Session = Depends(db)):
    if not b.consent:
        raise HTTPException(400, "Debes aceptar el tratamiento de datos personales")
    if b.role == "producer" and not (b.farm and b.municipality):
        raise HTTPException(400, "Finca y municipio son obligatorios para productores")
    if s.query(User).filter(or_(User.email == b.email.lower(), User.phone == b.phone)).first():
        raise HTTPException(409, "Este correo/celular ya tiene una cuenta")
    u = User(name=b.name.strip(), email=b.email.lower(), phone=b.phone, pw=hash_(b.password), role=b.role,
             farm=b.farm, municipality=b.municipality)
    s.add(u); s.commit()
    return session(u)


@app.post("/api/auth/login")
def login(b: Login, s: Session = Depends(db)):
    u = s.query(User).filter_by(email=b.email.lower()).first()
    if not u or not bcrypt.checkpw(b.password.encode(), u.pw.encode()):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    if not u.active:
        raise HTTPException(403, "Tu cuenta está suspendida")
    return session(u)


@app.get("/api/categories")
def categories(s: Session = Depends(db)):
    return [dict(id=c.id, name=c.name, active=c.active) for c in s.query(Category).order_by(Category.name)]


@app.post("/api/admin/categories", status_code=201)
def new_category(b: dict, u=Depends(need("admin")), s: Session = Depends(db)):
    name = str(b.get("name", "")).strip()
    if not name or s.query(Category).filter(func.lower(Category.name) == name.lower()).first():
        raise HTTPException(400, "Nombre vacío o categoría existente")
    s.add(Category(name=name)); s.commit()
    return {"ok": True}


@app.patch("/api/admin/categories/{cid}/toggle")
def toggle_category(cid: int, u=Depends(need("admin")), s: Session = Depends(db)):
    c = s.get(Category, cid) or HTTPException(404, "No existe")
    if isinstance(c, HTTPException): raise c
    c.active = not c.active; s.commit()
    return {"active": c.active}


@app.get("/api/admin/users")
def users(u=Depends(need("admin")), s: Session = Depends(db)):
    return [dict(id=x.id, name=x.name, email=x.email, role=x.role, active=x.active)
            for x in s.query(User).order_by(User.id)]


@app.patch("/api/admin/users/{uid}/toggle")
def toggle_user(uid: int, a=Depends(need("admin")), s: Session = Depends(db)):
    x = s.get(User, uid)
    if not x or x.id == a.id: raise HTTPException(400, "Operación no permitida")
    x.active = not x.active; s.commit()
    return {"active": x.active}


def check_product(b: ProductIn, s: Session):
    c = s.get(Category, b.category_id)
    if not c or not c.active: raise HTTPException(400, "Categoría no válida")
    if b.image and not (re.match(r"^data:image/(jpeg|png);base64,", b.image) and len(b.image) <= MAX_IMG):
        raise HTTPException(400, "La imagen debe ser JPG o PNG de máximo 5 MB")


@app.get("/api/products")
def products(q: str = "", category_id: Optional[int] = None, municipality: str = "",
             page: int = Query(1, ge=1), s: Session = Depends(db)):
    x = (s.query(Product).join(User, Product.producer_id == User.id)
         .filter(Product.visible, User.active, Product.stock > 0))
    if category_id: x = x.filter(Product.category_id == category_id)
    if municipality: x = x.filter(User.municipality == municipality)
    items = x.order_by(Product.id.desc()).all()
    if q:
        needle = normalize_text(q)
        items = [
            p for p in items
            if needle in normalize_text(p.name)
            or (p.description and needle in normalize_text(p.description))
        ]
    total = len(items)
    start = (page - 1) * PAGE
    page_items = items[start:start + PAGE]
    return dict(items=[pj(p) for p in page_items], total=total, page=page, pages=max(1, -(-total // PAGE)))


@app.get("/api/products/mine")
def my_products(u=Depends(need("producer")), s: Session = Depends(db)):
    return [pj(p) for p in s.query(Product).filter_by(producer_id=u.id).order_by(Product.id.desc())]


@app.get("/api/products/{pid}")
def product(pid: int, s: Session = Depends(db)):
    p = s.get(Product, pid)
    if not p or not p.visible or not p.producer.active: raise HTTPException(404, "Producto no disponible")
    return pj(p)


@app.post("/api/products", status_code=201)
def publish(b: ProductIn, u=Depends(need("producer")), s: Session = Depends(db)):
    check_product(b, s)
    s.add(Product(producer_id=u.id, **b.model_dump())); s.commit()
    return {"ok": True}


@app.put("/api/products/{pid}")
def edit(pid: int, b: ProductIn, u=Depends(need("producer")), s: Session = Depends(db)):
    p = s.get(Product, pid)
    if not p or p.producer_id != u.id: raise HTTPException(404, "Producto no encontrado")
    check_product(b, s)
    for k, v in b.model_dump().items(): setattr(p, k, v)
    s.commit()
    return {"ok": True}


@app.patch("/api/products/{pid}/toggle")
def hide(pid: int, u=Depends(need("producer")), s: Session = Depends(db)):
    p = s.get(Product, pid)
    if not p or p.producer_id != u.id: raise HTTPException(404, "Producto no encontrado")
    p.visible = not p.visible; s.commit()
    return {"visible": p.visible}


@app.post("/api/requests", status_code=201)
def create_request(b: ReqIn, u=Depends(need("consumer")), s: Session = Depends(db)):
    p = s.get(Product, b.product_id)
    if not p or not p.visible: raise HTTPException(404, "Producto no disponible")
    if b.quantity > p.stock: raise HTTPException(400, f"Solo hay {p.stock:g} {p.unit} disponibles")
    if b.date < date.today(): raise HTTPException(400, "La fecha no puede ser pasada")
    r = Req(consumer_id=u.id, product_id=p.id, qty=b.quantity, date=b.date, address=b.address,
            total=round(b.quantity * p.price, 2))
    s.add(r); s.commit()
    return {"id": r.id, "status": r.status, "total": r.total}


@app.get("/api/requests/mine")
def my_requests(u=Depends(need("consumer")), s: Session = Depends(db)):
    return [rj(r, wa=True) for r in s.query(Req).filter_by(consumer_id=u.id).order_by(Req.id.desc())]


@app.get("/api/requests/received")
def received(u=Depends(need("producer")), s: Session = Depends(db)):
    q = s.query(Req).join(Product).filter(Product.producer_id == u.id).order_by(Req.id.desc())
    return [rj(r, phone=True) for r in q]


@app.patch("/api/requests/{rid}")
def decide(rid: int, b: ReqUp, u=Depends(need("producer")), s: Session = Depends(db)):
    r = s.get(Req, rid)
    if not r or r.product.producer_id != u.id: raise HTTPException(404, "Solicitud no encontrada")
    ok = {"pending": ("accepted", "rejected"), "accepted": ("delivered",)}.get(r.status, ())
    if b.status not in ok: raise HTTPException(400, "Transición de estado no permitida")
    if b.status == "rejected" and not (b.reason or "").strip(): raise HTTPException(400, "El motivo es obligatorio")
    r.status, r.reason = b.status, (b.reason or None)
    s.commit()
    return {"status": r.status}


app.mount("/", StaticFiles(directory="static", html=True), name="web")
