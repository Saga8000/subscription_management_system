from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models import Product, ProductVariant, Tax, User
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    TaxCreate,
    TaxUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.services import audit_service

# --- Taxes --------------------------------------------------------------------------------


def list_taxes(db: Session) -> list[Tax]:
    return list(db.scalars(select(Tax).order_by(Tax.name)).all())


def create_tax(db: Session, data: TaxCreate, actor: User) -> Tax:
    tax = Tax(**data.model_dump())
    db.add(tax)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="tax.create", entity_type="tax", entity_id=tax.id)
    db.commit()
    return tax


def update_tax(db: Session, tax_id: int, data: TaxUpdate, actor: User) -> Tax:
    tax = db.get(Tax, tax_id)
    if tax is None:
        raise NotFoundError("Tax not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            raise BusinessRuleError(f"{field} cannot be empty.", fields={field: "Required"})
        setattr(tax, field, value)
    audit_service.record(db, actor_id=actor.id, action="tax.update", entity_type="tax", entity_id=tax.id)
    db.commit()
    return tax


# --- Products -----------------------------------------------------------------------------


def _load(db: Session, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.tax))
    )
    if product is None:
        raise NotFoundError("Product not found.")
    return product


def get_product(db: Session, product_id: int) -> Product:
    return _load(db, product_id)


def _check_tax(db: Session, tax_id: int | None) -> None:
    if tax_id is not None and db.get(Tax, tax_id) is None:
        raise BusinessRuleError("Selected tax does not exist.", fields={"tax_id": "Unknown tax"})


def _check_variant_price(product: Product, extra_price: object, field: str) -> None:
    if product.sales_price + extra_price < 0:  # type: ignore[operator]
        raise BusinessRuleError(
            "Variant price (base price + extra) cannot be negative.", fields={field: "Too low"}
        )


def create_product(db: Session, data: ProductCreate, actor: User) -> Product:
    _check_tax(db, data.tax_id)
    names = [v.name.lower() for v in data.variants]
    if len(names) != len(set(names)):
        raise BusinessRuleError("Variant names must be unique.", fields={"variants": "Duplicate name"})
    product = Product(**data.model_dump(exclude={"variants"}))
    for variant in data.variants:
        _check_variant_price(product, variant.extra_price, "variants")
        product.variants.append(ProductVariant(**variant.model_dump()))
    db.add(product)
    db.flush()
    audit_service.record(db, actor_id=actor.id, action="product.create", entity_type="product", entity_id=product.id)
    db.commit()
    return _load(db, product.id)


def update_product(db: Session, product_id: int, data: ProductUpdate, actor: User) -> Product:
    product = _load(db, product_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "product_type", "sales_price", "cost_price", "is_active"):
        if required in changes and changes[required] is None:
            raise BusinessRuleError(f"{required} cannot be empty.", fields={required: "Required"})
    if "tax_id" in changes:
        _check_tax(db, changes["tax_id"])
    for field, value in changes.items():
        setattr(product, field, value)
    for variant in product.variants:
        _check_variant_price(product, variant.extra_price, "sales_price")
    audit_service.record(db, actor_id=actor.id, action="product.update", entity_type="product", entity_id=product.id)
    db.commit()
    return _load(db, product.id)


def add_variant(db: Session, product_id: int, data: VariantCreate, actor: User) -> Product:
    product = _load(db, product_id)
    if any(v.name.lower() == data.name.lower() for v in product.variants):
        raise BusinessRuleError("A variant with this name already exists.", fields={"name": "Duplicate"})
    _check_variant_price(product, data.extra_price, "extra_price")
    product.variants.append(ProductVariant(**data.model_dump()))
    audit_service.record(db, actor_id=actor.id, action="product.variant_add", entity_type="product", entity_id=product.id)
    db.commit()
    return _load(db, product.id)


def update_variant(
    db: Session, product_id: int, variant_id: int, data: VariantUpdate, actor: User
) -> Product:
    product = _load(db, product_id)
    variant = next((v for v in product.variants if v.id == variant_id), None)
    if variant is None:
        raise NotFoundError("Variant not found.")
    changes = data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise BusinessRuleError("Fields cannot be empty.")
    if "name" in changes and any(
        v.id != variant.id and v.name.lower() == changes["name"].lower() for v in product.variants
    ):
        raise BusinessRuleError("A variant with this name already exists.", fields={"name": "Duplicate"})
    if "extra_price" in changes:
        _check_variant_price(product, changes["extra_price"], "extra_price")
    for field, value in changes.items():
        setattr(variant, field, value)
    audit_service.record(db, actor_id=actor.id, action="product.variant_update", entity_type="product", entity_id=product.id)
    db.commit()
    return _load(db, product.id)
