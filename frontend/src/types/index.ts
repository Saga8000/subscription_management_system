// Mirrors backend Pydantic output models. Decimal values are serialised as strings.
export type Money = string;
export type Role = "admin" | "staff" | "customer";
export type BillingPeriod = "daily" | "weekly" | "monthly" | "yearly";
export type QuotationStatus = "draft" | "sent" | "confirmed" | "cancelled";
export type SubscriptionStatus = "confirmed" | "active" | "paused" | "closed";
export type InvoiceStatus = "draft" | "confirmed" | "paid" | "cancelled";
export type PaymentMethod = "cash" | "bank_transfer" | "card" | "upi" | "cheque" | "other";
export type DiscountType = "percentage" | "fixed";
export type ProductType = "service" | "goods";

export interface Page<T> { items: T[]; total: number; page: number; page_size: number; }

export interface User { id: number; email: string; full_name: string; role: Role; is_active: boolean; customer_id: number | null; }

export interface Customer { id: number; name: string; email: string; phone: string | null; address: string | null; is_active: boolean; user_id: number | null; }

export interface Tax { id: number; name: string; rate_percent: string; is_active: boolean; }
export interface Variant { id: number; name: string; extra_price: Money; unit_price: Money; is_active: boolean; }
export interface Product {
  id: number; name: string; product_type: ProductType; sales_price: Money; cost_price: Money;
  notes: string | null; tax_id: number | null; tax: Tax | null; is_active: boolean; variants: Variant[];
}

export interface Plan {
  id: number; name: string; billing_period: BillingPeriod; billing_interval: number; min_quantity: number;
  available_from: string | null; available_until: string | null; duration_periods: number | null;
  is_closable: boolean; is_pausable: boolean; is_renewable: boolean; auto_close: boolean; is_active: boolean;
}

export interface LineOut {
  id: number; product_id: number; variant_id: number | null; description: string; quantity: string;
  unit_price: Money; tax_id: number | null; tax_rate: string; subtotal: Money; tax_amount: Money; total: Money;
}

export interface TemplateLine { id: number; product_id: number; variant_id: number | null; quantity: string; }
export interface QuotationTemplate {
  id: number; name: string; plan_id: number; validity_days: number; notes: string | null; is_active: boolean; lines: TemplateLine[];
}

export interface QuotationListItem {
  id: number; number: string; customer_id: number; customer_name: string; plan_name: string; status: QuotationStatus;
  quotation_date: string; expiration_date: string; start_date: string; is_expired: boolean;
}
export interface Quotation extends Omit<QuotationListItem, "plan_name"> {
  plan_id: number; plan_name: string; template_id: number | null; payment_terms_days: number; notes: string | null;
  renewal_of_id: number | null; subscription_id: number | null; lines: LineOut[];
  untaxed_amount: Money; tax_total: Money; total: Money;
}

export interface SubscriptionListItem {
  id: number; number: string; customer_id: number; customer_name: string; plan_name: string; status: SubscriptionStatus;
  start_date: string; expiry_date: string | null; next_invoice_date: string; recurring_total: Money;
}
export interface Subscription extends Omit<SubscriptionListItem, "recurring_total"> {
  plan_id: number; billing_period: BillingPeriod; billing_interval: number;
  is_closable: boolean; is_pausable: boolean; is_renewable: boolean;
  quotation_id: number; quotation_number: string; payment_terms_days: number;
  activated_at: string | null; paused_at: string | null; closed_at: string | null; close_reason: string | null;
  lines: LineOut[]; untaxed_amount: Money; tax_total: Money; recurring_total: Money;
}

export interface Payment {
  id: number; invoice_id: number; amount: Money; method: PaymentMethod; payment_date: string;
  reference: string | null; note: string | null; created_at: string;
}
export interface PaymentListItem extends Payment { invoice_number: string; customer_name: string; }

export interface InvoiceLine {
  id: number; product_id: number | null; variant_id: number | null; description: string; quantity: string;
  unit_price: Money; line_subtotal: Money; discount_amount: Money; tax_name: string | null; tax_rate: string;
  tax_amount: Money; line_total: Money;
}
export interface InvoiceListItem {
  id: number; number: string; subscription_id: number; customer_id: number; customer_name: string; status: InvoiceStatus;
  invoice_date: string; due_date: string; period_start: string; period_end: string;
  total: Money; amount_paid: Money; amount_due: Money; is_overdue: boolean;
}
export interface Invoice extends InvoiceListItem {
  subscription_number: string; customer_email: string; customer_address: string | null;
  subtotal: Money; discount_total: Money; discount_description: string | null; untaxed_amount: Money; tax_total: Money;
  confirmed_at: string | null; paid_at: string | null; cancelled_at: string | null;
  lines: InvoiceLine[]; payments: Payment[];
}

export interface BillingRunResult {
  as_of: string; subscriptions_checked: number; invoices_created: string[]; subscriptions_closed: string[];
  failures: { subscription_id: number; subscription_number: string; error: string }[];
}

export interface Discount {
  id: number; name: string; discount_type: DiscountType; value: Money; min_purchase_amount: Money | null;
  min_quantity: string | null; valid_from: string | null; valid_until: string | null; usage_limit: number | null;
  usage_count: number; is_active: boolean; product_ids: number[]; subscription_ids: number[];
}

export interface StatusCount { status: string; count: number; amount: Money | null; }
export interface Dashboard {
  period_start: string; period_end: string; as_of: string; active_subscriptions: number;
  revenue_collected: Money; amount_invoiced: Money; outstanding_balance: Money; overdue_count: number;
  overdue_amount: Money; monthly_recurring_revenue: Money; subscription_status: StatusCount[];
  invoice_status: StatusCount[]; monthly: { month: string; collected: Money; invoiced: Money }[];
  recent_payments: PaymentListItem[];
}
