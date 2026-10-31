from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import is_internal, require_admin, require_any_user, require_staff
from app.dependencies import get_db
from app.models import Product, User
from app.models.enums import ProductType
from app.schemas.product import (
    ProductCreate,
    ProductOut,
    ProductUpdate,
    TaxCreate,
    TaxOut,
    TaxUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.services import product_service
from app.utils.pagination import Page, PageParams, paginate

router = APIRouter()


@router.get("/taxes", response_model=list[TaxOut], tags=["taxes"])
def list_taxes(db: Session = Depends(get_db), _: User = Depends(require_staff)) -> list[TaxOut]:
    return [TaxOut.model_validate(t) for t in product_service.list_taxes(db)]


@router.post("/taxes", response_model=TaxOut, status_code=status.HTTP_201_CREATED, tags=["taxes"])
def create_tax(data: TaxCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> TaxOut:
    return TaxOut.model_validate(product_service.create_tax(db, data, actor))


@router.patch("/taxes/{tax_id}", response_model=TaxOut, tags=["taxes"])
def update_tax(
    tax_id: int, data: TaxUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)
) -> TaxOut:
    return TaxOut.model_validate(product_service.update_tax(db, tax_id, data, actor))


@router.get("/products", response_model=Page[ProductOut], tags=["products"])
def list_products(
    q: str | None = Query(None, max_length=100),
    active: bool | None = None,
    product_type: ProductType | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_user),
) -> Page[ProductOut]:
    stmt = (
        select(Product)
        .options(selectinload(Product.variants), selectinload(Product.tax))
        .order_by(Product.name, Product.id)
    )
    if not is_internal(user):
        active = True
    if active is not None:
        stmt = stmt.where(Product.is_active.is_(active))
    if product_type is not None:
        stmt = stmt.where(Product.product_type == product_type)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q.strip()}%"))
    items, total = paginate(db, stmt, params)
    return Page(items=[ProductOut.model_validate(p) for p in items], total=total, page=params.page, page_size=params.page_size)


@router.get("/products/{product_id}", response_model=ProductOut, tags=["products"])
def get_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_any_user)) -> ProductOut:
    return ProductOut.model_validate(product_service.get_product(db, product_id))


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED, tags=["products"])
def create_product(data: ProductCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)) -> ProductOut:
    return ProductOut.model_validate(product_service.create_product(db, data, actor))


@router.patch("/products/{product_id}", response_model=ProductOut, tags=["products"])
def update_product(
    product_id: int, data: ProductUpdate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> ProductOut:
    return ProductOut.model_validate(product_service.update_product(db, product_id, data, actor))


@router.post("/products/{product_id}/variants", response_model=ProductOut, status_code=status.HTTP_201_CREATED, tags=["products"])
def add_variant(
    product_id: int, data: VariantCreate, db: Session = Depends(get_db), actor: User = Depends(require_staff)
) -> ProductOut:
    return ProductOut.model_validate(product_service.add_variant(db, product_id, data, actor))


@router.patch("/products/{product_id}/variants/{variant_id}", response_model=ProductOut, tags=["products"])
def update_variant(
    product_id: int, variant_id: int, data: VariantUpdate,
    db: Session = Depends(get_db), actor: User = Depends(require_staff),
) -> ProductOut:
    return ProductOut.model_validate(product_service.update_variant(db, product_id, variant_id, data, actor))
