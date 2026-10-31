"""Import every model so Base.metadata is complete (used by Alembic and tests)."""

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.customer import Customer
from app.models.discount import Discount, discount_products, discount_subscriptions
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.quotation import Quotation, QuotationTemplate, QuotationTemplateLine
from app.models.quotation_line import QuotationLine
from app.models.subscription import Subscription
from app.models.subscription_line import SubscriptionLine
from app.models.tax import Tax
from app.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "Customer",
    "Discount",
    "Invoice",
    "InvoiceLine",
    "Payment",
    "Plan",
    "Product",
    "ProductVariant",
    "Quotation",
    "QuotationLine",
    "QuotationTemplate",
    "QuotationTemplateLine",
    "Subscription",
    "SubscriptionLine",
    "Tax",
    "User",
    "discount_products",
    "discount_subscriptions",
]
