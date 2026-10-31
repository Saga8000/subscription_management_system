from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"


class ProductType(str, Enum):
    SERVICE = "service"
    GOODS = "goods"


class BillingPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class QuotationStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"  # shown as "Quotation" in the UI
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class SubscriptionStatus(str, Enum):
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    UPI = "upi"
    CHEQUE = "cheque"
    OTHER = "other"


class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
