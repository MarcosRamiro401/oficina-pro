# app_oficina.py — API única para oficina (FastAPI + SQLite)
from __future__ import annotations
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import os
import uuid
import shutil

from fastapi import FastAPI, Depends, Header, HTTPException, status, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, String, Integer, DateTime, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

# ------------------------- Settings -------------------------
class Settings(BaseSettings):
    database_url: Optional[str] = None
    api_key: str = os.getenv("API_KEY", "oficinapro2024")
    app_name: str = "Oficina API (single-file)"
settings = Settings()

# ------------------------- DB -------------------------------
# Force SQLite for simplicity
DB_URL = "sqlite:///./oficina.sqlite3"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
class Base(DeclarativeBase): pass

# ------------------------- Models ---------------------------
class Company(Base):
    __tablename__="companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    cnpj: Mapped[Optional[str]] = mapped_column(String(20))
    slug: Mapped[Optional[str]] = mapped_column(String(80), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Client(Base):
    __tablename__="clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    is_company: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(200))
    document: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Vehicle(Base):
    __tablename__="vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    plate: Mapped[str] = mapped_column(String(16), index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(80))
    model: Mapped[Optional[str]] = mapped_column(String(120))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    renavam: Mapped[Optional[str]] = mapped_column(String(20))
    vin: Mapped[Optional[str]] = mapped_column(String(40))
    km_current: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Part(Base):
    __tablename__="parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(String(240))
    unit: Mapped[str] = mapped_column(String(16), default="UN")
    price_base: Mapped[float] = mapped_column(Float, default=0.0)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    has_invoice: Mapped[bool] = mapped_column(Boolean, default=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Supplier(Base):
    __tablename__="suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    cnpj: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class StockLot(Base):
    __tablename__="stock_lots"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class StockMovement(Base):
    __tablename__="stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    lot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stock_lots.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(16))  # IN/OUT
    qty: Mapped[float] = mapped_column(Float)
    ref_os_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_orders.id"))
    note: Mapped[Optional[str]] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Service(Base):
    __tablename__="services"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    description: Mapped[str] = mapped_column(String(240))
    default_hours: Mapped[float] = mapped_column(Float, default=1.0)
    labor_price_per_hour: Mapped[float] = mapped_column(Float, default=120.0)
    warranty_days: Mapped[int] = mapped_column(Integer, default=90)
    warranty_km: Mapped[int] = mapped_column(Integer, default=5000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WorkOrder(Base):
    __tablename__="work_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft/approved/closed
    km_in: Mapped[Optional[int]] = mapped_column(Integer)
    km_out: Mapped[Optional[int]] = mapped_column(Integer)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Client approval fields
    approval_token: Mapped[Optional[str]] = mapped_column(String(36), unique=True, nullable=True, index=True)
    approval_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)  # pending/approved/rejected/expired
    approval_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by_client_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Payment fields
    payment_method: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)  # cash/pix/credit_card/debit_card
    installments: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    final_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

class WorkOrderAttachment(Base):
    __tablename__="work_order_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(512))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WorkOrderItemService(Base):
    __tablename__="wo_item_services"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"), nullable=True)
    service_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # No default to distinguish new vs legacy
    price: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_hour_internal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # No default

class WorkOrderItemPart(Base):
    __tablename__="wo_item_parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    unit_cost_applied: Mapped[float] = mapped_column(Float, default=0.0)
    reserved: Mapped[bool] = mapped_column(Boolean, default=False)

class Invoice(Base):
    __tablename__="invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    discounts: Mapped[float] = mapped_column(Float, default=0.0)
    taxes_estimated: Mapped[float] = mapped_column(Float, default=0.0)
    gateway_fees: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="open")  # open/partial/paid
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Receivable(Base):
    __tablename__="receivables"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    method: Mapped[str] = mapped_column(String(24))
    amount: Mapped[float] = mapped_column(Float)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fee_percent: Mapped[float] = mapped_column(Float, default=0.0)
    fee_fixed: Mapped[float] = mapped_column(Float, default=0.0)
    txid: Mapped[Optional[str]] = mapped_column(String(120))
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IntegrationConfig(Base):
    __tablename__="integration_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(24), default="DUMMY")
    api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sandbox: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Add address column to clients table if it doesn't exist (migration)
try:
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('clients')]
    if 'address' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE clients ADD COLUMN address TEXT"))
            conn.commit()
except Exception as e:
    # Table doesn't exist yet or other error - will be created by create_all
    pass

# Add quantity column to parts table if it doesn't exist (migration)
try:
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('parts')]
    if 'quantity' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE parts ADD COLUMN quantity REAL NOT NULL DEFAULT 0"))
            conn.commit()
except Exception as e:
    # Table doesn't exist yet or other error - will be created by create_all
    pass

# Add service_description column to wo_item_services table (migration for new free-text services)
try:
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('wo_item_services')]
    if 'service_description' not in columns:
        with engine.connect() as conn:
            # Add the new service_description column
            conn.execute(text("ALTER TABLE wo_item_services ADD COLUMN service_description TEXT"))
            conn.commit()
except Exception as e:
    # Table doesn't exist yet or other error - will be created by create_all
    pass

# ------------------------- Schemas --------------------------
class CompanyCreate(BaseModel):
    name:str; cnpj:Optional[str]=None; slug:Optional[str]=None
class CompanyOut(BaseModel):
    id:int; name:str; cnpj:Optional[str]; slug:Optional[str]; created_at:datetime
    class Config: from_attributes=True

class ClientCreate(BaseModel):
    company_id:int; is_company:bool=False; name:str
    document:Optional[str]=None; email:Optional[str]=None; phone:Optional[str]=None; address:Optional[str]=None

class ClientUpdate(BaseModel):
    is_company:Optional[bool]=None; name:Optional[str]=None
    document:Optional[str]=None; email:Optional[str]=None; phone:Optional[str]=None; address:Optional[str]=None

class ClientOut(BaseModel):
    id:int; company_id:int; is_company:bool; name:str; document:Optional[str]; email:Optional[str]; phone:Optional[str]; address:Optional[str]; created_at:datetime
    class Config: from_attributes=True

class VehicleCreate(BaseModel):
    company_id:int; client_id:int; plate:str
    brand:Optional[str]=None; model:Optional[str]=None; year:Optional[int]=None
    renavam:Optional[str]=None; vin:Optional[str]=None; km_current:Optional[int]=None
class VehicleOut(BaseModel):
    id:int; company_id:int; client_id:int; plate:str; brand:Optional[str]; model:Optional[str]; year:Optional[int]; renavam:Optional[str]; vin:Optional[str]; km_current:Optional[int]; created_at:datetime
    class Config: from_attributes=True

class PartCreate(BaseModel):
    company_id:int; sku:str; description:str; unit:str="UN"; price_base:float=0.0; quantity:float=0.0; has_invoice:bool=False; supplier_id:Optional[int]=None
class PartOut(BaseModel):
    id:int; company_id:int; sku:str; description:str; unit:str; price_base:float; quantity:float; has_invoice:bool; supplier_id:Optional[int]; created_at:datetime
    class Config: from_attributes=True

class SupplierCreate(BaseModel):
    company_id:int; cnpj:Optional[str]=None; name:str; email:Optional[str]=None; phone:Optional[str]=None; address:Optional[str]=None
class SupplierOut(BaseModel):
    id:int; company_id:int; cnpj:Optional[str]; name:str; email:Optional[str]; phone:Optional[str]; address:Optional[str]; created_at:datetime
    class Config: from_attributes=True

class StockIn(BaseModel):
    company_id:int; part_id:int; qty:float=1.0; unit_cost:float=0.0
class StockMoveOut(BaseModel):
    id:int; company_id:int; part_id:int; lot_id:Optional[int]; type:str; qty:float; ref_os_id:Optional[int]; note:Optional[str]; created_at:datetime
    class Config: from_attributes=True

class ServiceCreate(BaseModel):
    company_id:int; description:str; default_hours:float=1.0; labor_price_per_hour:float=120.0
    warranty_days:int=90; warranty_km:int=5000
class ServiceOut(BaseModel):
    id:int; company_id:int; description:str; default_hours:float; labor_price_per_hour:float; warranty_days:int; warranty_km:int; created_at:datetime
    class Config: from_attributes=True

class WOItemServiceIn(BaseModel):
    # New format (free-text services)
    service_description:Optional[str]=None; 
    # Legacy format (catalog services)
    service_id:Optional[int]=None; hours:Optional[float]=None; cost_per_hour_internal:Optional[float]=None
    # Common fields
    price:float=0.0
    
    @model_validator(mode='after')
    def validate_service_type(self):
        # At least one of service_description or service_id must be provided
        if not self.service_description and not self.service_id:
            raise ValueError('Either service_description or service_id must be provided')
        return self
class WOItemPartIn(BaseModel):
    part_id:int; qty:float=1.0; unit_price:float=0.0

class WorkOrderCreate(BaseModel):
    company_id:int; client_id:int; vehicle_id:int; km_in:Optional[int]=None; notes:Optional[str]=None
    items_services:Optional[List[WOItemServiceIn]]=None
    items_parts:Optional[List[WOItemPartIn]]=None
class WorkOrderOut(BaseModel):
    id:int; company_id:int; client_id:int; vehicle_id:int; status:str; km_in:Optional[int]; km_out:Optional[int]; approved_at:Optional[datetime]; delivered_at:Optional[datetime]; notes:Optional[str]; created_at:datetime
    approval_token:Optional[str]=None; approval_status:Optional[str]=None; approval_expires_at:Optional[datetime]=None; approved_by_client_at:Optional[datetime]=None
    payment_method:Optional[str]=None; installments:Optional[int]=1; discount_percent:Optional[float]=0.0; final_amount:Optional[float]=None
    class Config: from_attributes=True

class InvoiceCreate(BaseModel):
    company_id:int; work_order_id:int; amount:float; discounts:float=0.0; taxes_estimated:float=0.0; gateway_fees:float=0.0
class ReceivableCreate(BaseModel):
    invoice_id:int; method:str; amount:float; fee_percent:float=0.0; fee_fixed:float=0.0; txid:Optional[str]=None; paid_at:Optional[datetime]=None
class InvoiceOut(BaseModel):
    id:int; company_id:int; work_order_id:int; amount:float; discounts:float; taxes_estimated:float; gateway_fees:float; status:str; created_at:datetime
    class Config: from_attributes=True
class ReceivableOut(BaseModel):
    id:int; invoice_id:int; method:str; amount:float; paid_at:Optional[datetime]; fee_percent:float; fee_fixed:float; txid:Optional[str]; reconciled:bool; created_at:datetime
    class Config: from_attributes=True

class ProfitBreakdown(BaseModel):
    revenue:float=0.0; part_costs:float=0.0; labor_costs:float=0.0; gateway_fees:float=0.0; taxes_estimated:float=0.0; other_costs:float=0.0; gross_profit:float=0.0; margin_pct:float=0.0

class ApprovalLinkResponse(BaseModel):
    approval_token:str; approval_link:str; expires_at:datetime

class ApprovalSubmitRequest(BaseModel):
    decision:str  # "approved" or "rejected"

class ApprovalDetailOut(BaseModel):
    work_order: WorkOrderOut
    company_name: str
    client_name: str
    vehicle_info: str
    items_services: List[Dict]
    items_parts: List[Dict]
    total: float

class PaymentCalculateRequest(BaseModel):
    payment_method: str  # cash/pix/credit_card/debit_card
    installments: int = 1  # 1-12 for credit_card, always 1 for others

class PaymentCalculateResponse(BaseModel):
    base_amount: float
    payment_method: str
    installments: int
    discount_percent: float
    discount_amount: float
    final_amount: float
    installment_value: float

# ------------------------- Security ------------------------
async def api_key_guard(x_api_key: Optional[str] = Header(default=None)):
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return True

def role_guard(allowed: List[str]):
    async def _guard(x_user_role: str = Header(default="")):
        role = (x_user_role or "").lower()
        if role not in [r.lower() for r in allowed]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' não autorizado; requer {allowed}")
        return True
    return _guard

# ------------------------- Helpers -------------------------
def db_dep():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def avg_cost_and_decrement(db: Session, company_id:int, part_id:int, qty:float) -> float:
    lots = db.query(StockLot).filter_by(company_id=company_id, part_id=part_id).all()
    tot_q = sum(l.qty for l in lots)
    if tot_q < qty: 
        # Se não tem estoque, apenas retorna custo zero e cria a OS sem baixar estoque
        return 0.0
    tot_v = sum(l.qty*l.unit_cost for l in lots)
    avg = (tot_v/tot_q) if tot_q else 0.0
    remaining = qty
    for l in lots:
        if remaining<=0: break
        take = min(l.qty, remaining)
        l.qty -= take
        remaining -= take
    return avg

# ------------------------- App & CORS ----------------------
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

@app.get("/health")
def health(): return {"ok": True, "app": settings.app_name}

# ------------------------- Companies/Clients/Vehicles ------
@app.post("/companies", response_model=CompanyOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager"]))])
def create_company(data: CompanyCreate, db: Session = Depends(db_dep)):
    obj = Company(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/companies", response_model=List[CompanyOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager"]))])
def list_companies(db: Session = Depends(db_dep)):
    return db.query(Company).all()

@app.post("/clients", response_model=ClientOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","sales"]))])
def create_client(data: ClientCreate, db: Session = Depends(db_dep)):
    obj = Client(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/clients", response_model=List[ClientOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","sales"]))])
def list_clients(company_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(Client)
    if company_id:
        query = query.filter(Client.company_id == company_id)
    return query.all()

@app.patch("/clients/{client_id}", response_model=ClientOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","sales"]))])
def update_client(client_id: int, data: ClientUpdate, x_company_id: int = Header(...), db: Session = Depends(db_dep)):
    # Multi-tenant security: Fetch client and verify it belongs to authenticated user's company
    client = db.query(Client).filter(Client.id == client_id, Client.company_id == x_company_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
    # Data safety: only update fields that were provided (exclude_unset=True)
    # This prevents nullifying fields that weren't sent and prevents company_id changes
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    db.commit(); db.refresh(client); return client

@app.delete("/clients/{client_id}", dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","sales"]))])
def delete_client(client_id: int, x_company_id: int = Header(...), db: Session = Depends(db_dep)):
    # Multi-tenant security: Fetch client and verify it belongs to authenticated user's company
    client = db.query(Client).filter(Client.id == client_id, Client.company_id == x_company_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
    db.delete(client); db.commit()
    return {"success": True, "message": "Client deleted successfully"}

@app.post("/vehicles", response_model=VehicleOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","sales"]))])
def create_vehicle(data: VehicleCreate, db: Session = Depends(db_dep)):
    obj = Vehicle(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/vehicles", response_model=List[VehicleOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","sales"]))])
def list_vehicles(company_id: Optional[int] = Query(None), client_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(Vehicle)
    if company_id:
        query = query.filter(Vehicle.company_id == company_id)
    if client_id:
        query = query.filter(Vehicle.client_id == client_id)
    return query.all()

# ------------------------- Parts/Stock ----------------------
@app.post("/parts", response_model=PartOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def create_part(data: PartCreate, db: Session = Depends(db_dep)):
    obj = Part(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/parts", response_model=List[PartOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def list_parts(company_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(Part)
    if company_id:
        query = query.filter(Part.company_id == company_id)
    return query.all()

@app.patch("/parts/{part_id}", response_model=PartOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def update_part(part_id: int, data: PartCreate, db: Session = Depends(db_dep)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    for key, value in data.model_dump().items():
        setattr(part, key, value)
    db.commit(); db.refresh(part); return part

@app.delete("/parts/{part_id}", dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def delete_part(part_id: int, db: Session = Depends(db_dep)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    db.delete(part); db.commit()
    return {"success": True, "message": "Part deleted successfully"}

@app.post("/parts/stock/in", response_model=StockMoveOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def stock_in(data: StockIn, db: Session = Depends(db_dep)):
    lot = StockLot(company_id=data.company_id, part_id=data.part_id, qty=data.qty, unit_cost=data.unit_cost)
    db.add(lot); db.flush()
    move = StockMovement(company_id=data.company_id, part_id=data.part_id, lot_id=lot.id, type="IN", qty=data.qty, note="Entrada de estoque")
    db.add(move); db.commit(); db.refresh(move); return move

# ------------------------- Suppliers ------------------------
@app.post("/suppliers", response_model=SupplierOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def create_supplier(data: SupplierCreate, db: Session = Depends(db_dep)):
    obj = Supplier(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/suppliers", response_model=List[SupplierOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","storekeeper","manager"]))])
def list_suppliers(company_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(Supplier)
    if company_id:
        query = query.filter(Supplier.company_id == company_id)
    return query.all()

# ------------------------- Services -------------------------
@app.post("/services", response_model=ServiceOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager"]))])
def create_service(data: ServiceCreate, db: Session = Depends(db_dep)):
    obj = Service(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@app.get("/services", response_model=List[ServiceOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager"]))])
def list_services(company_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(Service)
    if company_id:
        query = query.filter(Service.company_id == company_id)
    return query.all()

# ------------------------- Work Orders ---------------------
@app.post("/workorders", response_model=WorkOrderOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","mechanic"]))])
def create_workorder(data: WorkOrderCreate, db: Session = Depends(db_dep)):
    wo = WorkOrder(company_id=data.company_id, client_id=data.client_id, vehicle_id=data.vehicle_id, status="draft", km_in=data.km_in, notes=data.notes)
    db.add(wo); db.flush()
    if data.items_services:
        for s in data.items_services:
            # Determine format: new (service_description) or legacy (service_id)
            if s.service_description:
                # New format: free-text service, no hours/cost tracking
                # Use sentinel values (SQLite doesn't support nullable on existing columns)
                db.add(WorkOrderItemService(
                    work_order_id=wo.id,
                    service_id=0,  # Sentinel: 0 = free-text service (not from catalog)
                    service_description=s.service_description, 
                    price=s.price,
                    hours=0.0,  # Sentinel: 0 = no hour tracking (fixed price)
                    cost_per_hour_internal=0.0  # Sentinel: 0 = no internal cost tracking
                ))
            else:
                # Legacy format: catalog service with hours
                # Apply defaults if not provided to maintain backward compatibility
                hours = s.hours if s.hours is not None else 1.0
                cost_per_hour = s.cost_per_hour_internal if s.cost_per_hour_internal is not None else 60.0
                db.add(WorkOrderItemService(
                    work_order_id=wo.id, 
                    service_id=s.service_id, 
                    hours=hours, 
                    price=s.price, 
                    cost_per_hour_internal=cost_per_hour
                ))
    if data.items_parts:
        for p in data.items_parts:
            unit_cost = avg_cost_and_decrement(db, data.company_id, p.part_id, p.qty)
            db.add(WorkOrderItemPart(work_order_id=wo.id, part_id=p.part_id, qty=p.qty, unit_price=p.unit_price, unit_cost_applied=unit_cost, reserved=True))
            if unit_cost > 0:  # Só registra movimento se havia estoque
                db.add(StockMovement(company_id=data.company_id, part_id=p.part_id, lot_id=None, type="OUT", qty=p.qty, ref_os_id=wo.id, note="Reserva/Consumo OS"))
    db.commit(); db.refresh(wo); return wo

@app.get("/workorders", response_model=List[WorkOrderOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","mechanic"]))])
def list_workorders(company_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(WorkOrder)
    if company_id:
        query = query.filter(WorkOrder.company_id == company_id)
    return query.all()

@app.get("/workorders/{wo_id}", response_model=WorkOrderOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","mechanic"]))])
def get_workorder(wo_id:int, db: Session = Depends(db_dep)):
    wo = db.get(WorkOrder, wo_id)
    if not wo: raise HTTPException(404, "OS não encontrada")
    return wo

@app.post("/workorders/{wo_id}/approve", response_model=WorkOrderOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager"]))])
def approve_workorder(wo_id:int, db: Session = Depends(db_dep)):
    wo = db.get(WorkOrder, wo_id)
    if not wo: raise HTTPException(404, "OS não encontrada")
    wo.status="approved"; wo.approved_at=datetime.utcnow()
    db.commit(); db.refresh(wo); return wo

@app.get("/workorders/{wo_id}/profit", response_model=ProfitBreakdown, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","finance"]))])
def workorder_profit(wo_id:int, db: Session = Depends(db_dep)):
    wo = db.get(WorkOrder, wo_id)
    if not wo: raise HTTPException(404, "OS não encontrada")
    svc = db.query(WorkOrderItemService).filter_by(work_order_id=wo_id).all()
    itm = db.query(WorkOrderItemPart).filter_by(work_order_id=wo_id).all()
    # Revenue calculation
    # NEW format (hours=0 sentinel): price is the total
    # LEGACY format (hours>0): price is per-hour, multiply by hours
    revenue = sum((s.price * s.hours if s.hours > 0 else s.price) for s in svc) + sum(i.unit_price*i.qty for i in itm)
    # Labor costs - only for legacy format with cost_per_hour_internal>0 and hours>0
    labor_costs = sum((s.cost_per_hour_internal * s.hours if (s.cost_per_hour_internal > 0 and s.hours > 0) else 0) for s in svc)
    part_costs = sum(i.unit_cost_applied*i.qty for i in itm)
    inv = db.query(Invoice).filter_by(work_order_id=wo_id).order_by(Invoice.id.desc()).first()
    gateway_fees = inv.gateway_fees if inv else 0.0
    taxes_est = inv.taxes_estimated if inv else 0.0
    gross = revenue - (labor_costs + part_costs + gateway_fees + taxes_est)
    margin = (gross/revenue*100) if revenue else 0.0
    return ProfitBreakdown(revenue=revenue, part_costs=part_costs, labor_costs=labor_costs, gateway_fees=gateway_fees, taxes_estimated=taxes_est, other_costs=0.0, gross_profit=gross, margin_pct=margin)

# ---------------------- Client Approval --------------------
@app.post("/workorders/{wo_id}/generate-approval", response_model=ApprovalLinkResponse, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager"]))])
def generate_approval_link(wo_id:int, db: Session = Depends(db_dep)):
    """Generate a unique approval token for client to approve/reject work order"""
    wo = db.get(WorkOrder, wo_id)
    if not wo: raise HTTPException(404, "OS não encontrada")
    
    # Generate unique token
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=7)  # Expires in 7 days
    
    # Update work order
    wo.approval_token = token
    wo.approval_status = "pending"
    wo.approval_expires_at = expires_at
    wo.approved_by_client_at = None
    
    db.commit()
    
    # Generate approval link (frontend will be at same domain)
    approval_link = f"/approve/{token}"
    
    return ApprovalLinkResponse(
        approval_token=token,
        approval_link=approval_link,
        expires_at=expires_at
    )

@app.get("/approve/{token}", response_model=ApprovalDetailOut)
def get_approval_details(token:str, db: Session = Depends(db_dep)):
    """Public endpoint: Get work order details for client approval"""
    wo = db.query(WorkOrder).filter(WorkOrder.approval_token == token).first()
    if not wo: raise HTTPException(404, "Link de aprovação inválido ou expirado")
    
    # Check if expired
    if wo.approval_expires_at and datetime.utcnow() > wo.approval_expires_at:
        wo.approval_status = "expired"
        db.commit()
        raise HTTPException(410, "Link de aprovação expirado")
    
    # Check if already processed
    if wo.approval_status in ["approved", "rejected"]:
        raise HTTPException(409, f"Orçamento já foi {wo.approval_status}")
    
    # Get related data
    company = db.get(Company, wo.company_id)
    client = db.get(Client, wo.client_id)
    vehicle = db.get(Vehicle, wo.vehicle_id)
    
    # Get services and parts
    services = db.query(WorkOrderItemService).filter_by(work_order_id=wo.id).all()
    parts = db.query(WorkOrderItemPart).filter_by(work_order_id=wo.id).all()
    
    items_services = []
    for svc in services:
        # Use service_description if available (new format), otherwise get from service catalog (old format)
        if svc.service_description:
            description = svc.service_description
        elif svc.service_id:
            service = db.get(Service, svc.service_id)
            description = service.description if service else "Serviço"
        else:
            description = "Serviço"
        
        # For new format (no hours), total is just price
        # For old format (has hours), total is hours * price
        total = (svc.hours * svc.price) if svc.hours else svc.price
        
        items_services.append({
            "description": description,
            "hours": svc.hours or 0,
            "price_per_hour": svc.price if svc.hours else svc.price,  # For new format, price is total
            "total": total
        })
    
    items_parts = []
    for prt in parts:
        part = db.get(Part, prt.part_id)
        items_parts.append({
            "description": part.description if part else "Peça",
            "sku": part.sku if part else "",
            "qty": prt.qty,
            "unit_price": prt.unit_price,
            "total": prt.qty * prt.unit_price
        })
    
    total = sum(s["total"] for s in items_services) + sum(p["total"] for p in items_parts)
    
    vehicle_info = vehicle.plate if vehicle else ""
    if vehicle and (vehicle.brand or vehicle.model):
        vehicle_info += f" - {vehicle.brand or ''} {vehicle.model or ''}".strip()
    
    return ApprovalDetailOut(
        work_order=WorkOrderOut.model_validate(wo),
        company_name=company.name if company else "",
        client_name=client.name if client else "",
        vehicle_info=vehicle_info,
        items_services=items_services,
        items_parts=items_parts,
        total=total
    )

@app.post("/approve/{token}/submit")
def submit_approval(token:str, data: ApprovalSubmitRequest, db: Session = Depends(db_dep)):
    """Public endpoint: Client approves or rejects work order"""
    wo = db.query(WorkOrder).filter(WorkOrder.approval_token == token).first()
    if not wo: raise HTTPException(404, "Link de aprovação inválido")
    
    # Check if expired
    if wo.approval_expires_at and datetime.utcnow() > wo.approval_expires_at:
        wo.approval_status = "expired"
        db.commit()
        raise HTTPException(410, "Link de aprovação expirado")
    
    # Check if already processed
    if wo.approval_status in ["approved", "rejected"]:
        raise HTTPException(409, f"Orçamento já foi {wo.approval_status}")
    
    # Validate decision
    if data.decision not in ["approved", "rejected"]:
        raise HTTPException(400, "Decisão inválida. Use 'approved' ou 'rejected'")
    
    # Update work order
    wo.approval_status = data.decision
    wo.approved_by_client_at = datetime.utcnow()
    
    # If approved by client, also update the main status
    if data.decision == "approved":
        wo.status = "approved"
        wo.approved_at = datetime.utcnow()
    
    db.commit()
    db.refresh(wo)
    
    return {
        "success": True,
        "decision": data.decision,
        "message": "Orçamento aprovado com sucesso!" if data.decision == "approved" else "Orçamento recusado.",
        "work_order_id": wo.id
    }

# ---------------------- Payment Calculation -----------------
@app.post("/workorders/{wo_id}/calculate-payment", response_model=PaymentCalculateResponse, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","finance"]))])
def calculate_payment(wo_id:int, data: PaymentCalculateRequest, db: Session = Depends(db_dep)):
    """Calculate payment with discounts/fees based on payment method and installments"""
    wo = db.get(WorkOrder, wo_id)
    if not wo: raise HTTPException(404, "OS não encontrada")
    
    # Calculate base amount from services and parts
    services = db.query(WorkOrderItemService).filter_by(work_order_id=wo_id).all()
    parts = db.query(WorkOrderItemPart).filter_by(work_order_id=wo_id).all()
    base_amount = sum(s.price * s.hours for s in services) + sum(p.unit_price * p.qty for p in parts)
    
    # Validate payment method
    if data.payment_method not in ["cash", "pix", "credit_card", "debit_card"]:
        raise HTTPException(400, "Método de pagamento inválido")
    
    # Validate installments
    if data.installments < 1 or data.installments > 12:
        raise HTTPException(400, "Número de parcelas inválido (1-12)")
    
    # Validate installments for non-credit methods (must be 1)
    if data.payment_method in ["cash", "pix", "debit_card"] and data.installments > 1:
        raise HTTPException(400, "Pagamentos à vista não permitem parcelamento")
    
    # Calculate discount based on payment method
    discount_percent = 0.0
    if data.payment_method in ["cash", "pix", "debit_card"]:
        # 10% discount for cash/pix/debit (pagamento à vista)
        discount_percent = 10.0
    elif data.payment_method == "credit_card":
        # No discount for credit card
        discount_percent = 0.0
    
    discount_amount = base_amount * (discount_percent / 100.0)
    final_amount = base_amount - discount_amount
    
    # Calculate installment value
    installment_value = final_amount / data.installments if data.installments > 0 else final_amount
    
    # Update work order with payment info
    wo.payment_method = data.payment_method
    wo.installments = data.installments
    wo.discount_percent = discount_percent
    wo.final_amount = final_amount
    db.commit()
    
    return PaymentCalculateResponse(
        base_amount=base_amount,
        payment_method=data.payment_method,
        installments=data.installments,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        final_amount=final_amount,
        installment_value=installment_value
    )

# ------------------------- Finance -------------------------
class _DummyProvider:
    def pix(self, amount:float, meta:Dict): return {"provider":"DUMMY","method":"PIX","amount":amount,"copy_paste":f"PIX-{meta.get('invoice_id')}-{int(amount*100)}"}
    def boleto(self, amount:float, meta:Dict): return {"provider":"DUMMY","method":"BOLETO","amount":amount,"digitable_line":"23790..."}
    def link(self, amount:float, meta:Dict): return {"provider":"DUMMY","method":"LINK","amount":amount,"checkout_url":"https://pay.example/abc"}

def _provider_for_company(_:Session, __:int): return _DummyProvider()

@app.post("/finance/invoices", response_model=InvoiceOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","finance","manager"]))])
def create_invoice(data: InvoiceCreate, db: Session = Depends(db_dep)):
    inv = Invoice(**data.model_dump(), status="open"); db.add(inv); db.commit(); db.refresh(inv); return inv

@app.get("/invoices", response_model=List[InvoiceOut], dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","finance","manager"]))])
def list_invoices(company_id: Optional[int] = Query(None), db: Session = Depends(db_dep)):
    query = db.query(Invoice)
    if company_id:
        query = query.filter(Invoice.company_id == company_id)
    return query.all()

@app.post("/finance/receivables", response_model=ReceivableOut, dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","finance","manager"]))])
def create_receivable(data: ReceivableCreate, db: Session = Depends(db_dep)):
    inv = db.get(Invoice, data.invoice_id)
    if not inv: raise HTTPException(404, "Fatura não encontrada")
    rec = Receivable(**data.model_dump()); db.add(rec)
    paid = sum((r.amount for r in db.query(Receivable).filter_by(invoice_id=inv.id).all() if r.paid_at)) + (data.amount if data.paid_at else 0)
    if paid >= inv.amount: inv.status="paid"
    elif paid>0: inv.status="partial"
    db.commit(); db.refresh(rec); db.refresh(inv); return rec

@app.post("/finance/charge/pix/{invoice_id}", dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","finance","manager"]))])
def pix_charge(invoice_id:int, db: Session = Depends(db_dep)):
    inv = db.get(Invoice, invoice_id)
    if not inv: raise HTTPException(404, "Fatura não encontrada")
    return _provider_for_company(db, inv.company_id).pix(inv.amount, {"invoice_id":inv.id})

@app.post("/finance/charge/boleto/{invoice_id}", dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","finance","manager"]))])
def boleto(invoice_id:int, db: Session = Depends(db_dep)):
    inv = db.get(Invoice, invoice_id)
    if not inv: raise HTTPException(404, "Fatura não encontrada")
    return _provider_for_company(db, inv.company_id).boleto(inv.amount, {"invoice_id":inv.id})

@app.post("/finance/charge/card/{invoice_id}", dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","finance","manager"]))])
def card(invoice_id:int, db: Session = Depends(db_dep)):
    inv = db.get(Invoice, invoice_id)
    if not inv: raise HTTPException(404, "Fatura não encontrada")
    return _provider_for_company(db, inv.company_id).link(inv.amount, {"invoice_id":inv.id})

# ------------------------- Messaging -------------------------
class SendMessageRequest(BaseModel):
    phone: str
    message: str
    client_id: Optional[int] = None

class SendMessageResponse(BaseModel):
    success: bool
    message: str
    provider: str

class AttachmentOut(BaseModel):
    id: int
    work_order_id: int
    filename: str
    uploaded_at: datetime
    class Config: from_attributes=True

@app.post("/messaging/send", response_model=SendMessageResponse, dependencies=[Depends(api_key_guard)])
def send_message(data: SendMessageRequest, db: Session = Depends(db_dep)):
    """
    Send WhatsApp/SMS message to client.
    
    Currently using placeholder - returns success without actually sending.
    To enable real sending:
    1. Set environment variables:
       - TWILIO_ACCOUNT_SID
       - TWILIO_AUTH_TOKEN
       - TWILIO_PHONE_NUMBER
    Or use WhatsApp Business API credentials
    2. Uncomment the integration code below
    """
    
    # PLACEHOLDER: Simulate successful send
    # TODO: Replace with real Twilio/WhatsApp Business API integration
    
    # Example Twilio integration (commented out):
    # from twilio.rest import Client
    # account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    # auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    # twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
    # 
    # if account_sid and auth_token and twilio_phone:
    #     client = Client(account_sid, auth_token)
    #     message = client.messages.create(
    #         body=data.message,
    #         from_=twilio_phone,
    #         to=data.phone
    #     )
    #     return SendMessageResponse(
    #         success=True,
    #         message=f"Message sent successfully via Twilio (SID: {message.sid})",
    #         provider="twilio"
    #     )
    
    # For now, just log and return success
    print(f"[PLACEHOLDER] Would send message to {data.phone}: {data.message}")
    
    return SendMessageResponse(
        success=True,
        message="Message simulated successfully (placeholder mode)",
        provider="placeholder"
    )

# ------------------------- Reports -------------------------
@app.get("/reports/dre", dependencies=[Depends(api_key_guard), Depends(role_guard(["admin","manager","finance"]))])
def dre(company_id:int, start:str = Query(...), end:str = Query(...), db: Session = Depends(db_dep)):
    dt_s = datetime.fromisoformat(start+" 00:00:00"); dt_e = datetime.fromisoformat(end+" 23:59:59")
    invs = db.query(Invoice).filter(Invoice.company_id==company_id, Invoice.created_at>=dt_s, Invoice.created_at<=dt_e).all()
    revenue = sum(i.amount - i.discounts for i in invs if i.status in ("paid","partial","open"))
    fees = sum(i.gateway_fees for i in invs); taxes = sum(i.taxes_estimated for i in invs)
    labor=parts=0.0
    for i in invs:
        s = db.query(WorkOrderItemService).filter_by(work_order_id=i.work_order_id).all()
        p = db.query(WorkOrderItemPart).filter_by(work_order_id=i.work_order_id).all()
        labor += sum(x.cost_per_hour_internal*x.hours for x in s)
        parts += sum(x.unit_cost_applied*x.qty for x in p)
    gross = revenue - (labor + parts + fees + taxes)
    return {"period":{"start":start,"end":end},"company_id":company_id,"revenue":round(revenue,2),"costs":{"labor":round(labor,2),"parts":round(parts,2),"fees":round(fees,2),"taxes":round(taxes,2)},"gross_profit":round(gross,2),"margin_pct": round((gross/revenue*100) if revenue else 0.0, 2)}

# Attachment endpoints
@app.post("/workorders/{wo_id}/attachments", response_model=AttachmentOut, dependencies=[Depends(api_key_guard)])
async def upload_attachment(wo_id: int, file: UploadFile = File(...), db: Session = Depends(db_dep)):
    wo = db.query(WorkOrder).filter_by(id=wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    
    filename = f"{uuid.uuid4()}_{file.filename}"
    stored_path = f"attachments/{filename}"
    
    with open(stored_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    att = WorkOrderAttachment(work_order_id=wo_id, filename=file.filename, stored_path=stored_path)
    db.add(att)
    db.commit()
    db.refresh(att)
    return att

@app.get("/workorders/{wo_id}/attachments", response_model=list[AttachmentOut], dependencies=[Depends(api_key_guard)])
def list_attachments(wo_id: int, db: Session = Depends(db_dep)):
    return db.query(WorkOrderAttachment).filter_by(work_order_id=wo_id).all()

@app.get("/attachments/{att_id}")
def download_attachment(att_id: int, db: Session = Depends(db_dep)):
    att = db.query(WorkOrderAttachment).filter_by(id=att_id).first()
    if not att or not os.path.exists(att.stored_path):
        raise HTTPException(404, "Attachment not found")
    return FileResponse(att.stored_path, filename=att.filename)
