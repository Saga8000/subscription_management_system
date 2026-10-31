import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorMessage, fieldErrors } from "../api/client";
import { ConfirmDialog, Empty, ErrorAlert, Field, Loading, Modal, PageHeader, Pagination, StatusBadge, useAsync } from "../components/ui";
import { isInternal, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Invoice, InvoiceListItem, Page, PaymentMethod } from "../types";
import { formatDate, label, money, today } from "../utils/format";

export function InvoiceTable({ items }: { items: InvoiceListItem[] }) {
  const navigate = useNavigate();
  return (
    <div className="table-wrap"><table>
      <thead><tr><th>Number</th><th>Customer</th><th>Period</th><th>Due</th><th className="num">Total</th><th className="num">Paid</th><th className="num">Due amount</th><th>Status</th></tr></thead>
      <tbody>{items.map((i) => (
        <tr key={i.id} className="clickable" onClick={() => navigate(`/invoices/${i.id}`)}>
          <td><Link to={`/invoices/${i.id}`}>{i.number}</Link></td><td>{i.customer_name}</td>
          <td>{formatDate(i.period_start)} – {formatDate(i.period_end)}</td><td>{formatDate(i.due_date)}</td>
          <td className="num">{money(i.total)}</td><td className="num">{money(i.amount_paid)}</td><td className="num">{money(i.amount_due)}</td>
          <td>{i.is_overdue ? <StatusBadge status="overdue" /> : <StatusBadge status={i.status} />}</td>
        </tr>
      ))}</tbody>
    </table></div>
  );
}

export function InvoicesPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const overdue = params.get("overdue") ?? "";
  const customerId = params.get("customer_id");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(
    () => api.get<Page<InvoiceListItem>>("/invoices", { status, overdue, q, page, customer_id: customerId }),
    [status, overdue, q, page, customerId],
  );
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
    setPage(1);
  };
  return (
    <>
      <PageHeader title="Invoices" subtitle={customerId ? <>Filtered by customer · <Link to="/invoices">clear</Link></> : undefined} />
      <div className="filters">
        <select value={status} onChange={(e) => update("status", e.target.value)}>
          <option value="">All statuses</option><option value="draft">Draft</option><option value="confirmed">Confirmed (unpaid)</option>
          <option value="paid">Paid</option><option value="cancelled">Cancelled</option>
        </select>
        <label className="check"><input type="checkbox" checked={overdue === "true"} onChange={(e) => update("overdue", e.target.checked ? "true" : "")} /> Overdue only</label>
        <input placeholder="Search number" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No invoices found.</Empty> : data && <InvoiceTable items={data.items} />}
        <Pagination page={data} onPage={setPage} />
      </div>
    </>
  );
}

export function InvoiceDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { data: inv, error, loading, reload, setData } = useAsync(() => api.get<Invoice>(`/invoices/${id}`), [id]);
  const [action, setAction] = useState<"confirm" | "cancel" | "pay" | null>(null);
  if (loading && !inv) return <Loading />;
  if (!inv) return <ErrorAlert message={error} onRetry={reload} />;
  const internal = isInternal(user);
  const run = async (name: string, message: string) => {
    setData(await api.post<Invoice>(`/invoices/${inv.id}/${name}`));
    toast.success(message);
  };
  return (
    <>
      <PageHeader
        title={`Invoice ${inv.number}`}
        subtitle={<>{inv.customer_name} · <Link to={`/subscriptions/${inv.subscription_id}`}>{inv.subscription_number}</Link> {inv.is_overdue ? <StatusBadge status="overdue" /> : <StatusBadge status={inv.status} />}</>}
        actions={<>
          {internal && inv.status === "draft" && <button className="btn btn-primary" onClick={() => setAction("confirm")}>Confirm</button>}
          {internal && inv.status === "confirmed" && <button className="btn btn-primary" onClick={() => setAction("pay")}>Record payment</button>}
          {internal && (inv.status === "draft" || (inv.status === "confirmed" && Number(inv.amount_paid) === 0)) && <button className="btn btn-danger" onClick={() => setAction("cancel")}>Cancel</button>}
          <button className="btn" onClick={() => window.print()}>Print</button>
        </>}
      />
      <ErrorAlert message={error} />
      <div className="card">
        <dl className="details">
          <dt>Bill to</dt><dd>{inv.customer_name}<br />{inv.customer_email}{inv.customer_address && <><br />{inv.customer_address}</>}</dd>
          <dt>Invoice date</dt><dd>{formatDate(inv.invoice_date)}</dd>
          <dt>Billing period</dt><dd>{formatDate(inv.period_start)} – {formatDate(inv.period_end)}</dd>
          <dt>Due date</dt><dd>{formatDate(inv.due_date)}</dd>
        </dl>
      </div>
      <div className="card">
        <div className="table-wrap"><table>
          <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Unit price</th><th className="num">Discount</th><th>Tax</th><th className="num">Tax amt</th><th className="num">Total</th></tr></thead>
          <tbody>{inv.lines.map((l) => (
            <tr key={l.id}><td>{l.description}</td><td className="num">{Number(l.quantity)}</td><td className="num">{money(l.unit_price)}</td>
              <td className="num">{Number(l.discount_amount) ? `−${money(l.discount_amount)}` : "—"}</td>
              <td>{l.tax_name ? `${l.tax_name} ${Number(l.tax_rate)}%` : "—"}</td><td className="num">{money(l.tax_amount)}</td><td className="num">{money(l.line_total)}</td></tr>
          ))}</tbody>
        </table></div>
        <div className="totals" style={{ marginTop: 12 }}>
          <div><span>Subtotal</span><span>{money(inv.subtotal)}</span></div>
          {Number(inv.discount_total) > 0 && <div><span>Discount{inv.discount_description ? ` (${inv.discount_description})` : ""}</span><span>−{money(inv.discount_total)}</span></div>}
          <div><span>Untaxed</span><span>{money(inv.untaxed_amount)}</span></div>
          <div><span>Tax</span><span>{money(inv.tax_total)}</span></div>
          <div className="grand"><span>Total</span><span>{money(inv.total)}</span></div>
          <div><span>Paid</span><span>{money(inv.amount_paid)}</span></div>
          <div className="grand"><span>Amount due</span><span>{money(inv.amount_due)}</span></div>
        </div>
      </div>
      <div className="card">
        <h2>Payments</h2>
        {inv.payments.length === 0 ? <div className="muted">No payments recorded.</div> : (
          <table><thead><tr><th>Date</th><th>Method</th><th>Reference</th><th className="num">Amount</th></tr></thead>
            <tbody>{inv.payments.map((p) => <tr key={p.id}><td>{formatDate(p.payment_date)}</td><td>{label(p.method)}</td><td>{p.reference ?? "—"}</td><td className="num">{money(p.amount)}</td></tr>)}</tbody></table>
        )}
      </div>
      {action === "confirm" && <ConfirmDialog title="Confirm invoice?" message="Confirmed invoices are visible to the customer and can receive payments. Lines can no longer change." onConfirm={() => run("confirm", "Invoice confirmed.")} onClose={() => setAction(null)} />}
      {action === "cancel" && <ConfirmDialog danger title="Cancel invoice?" confirmLabel="Cancel invoice" message="If this is the latest period of the subscription, that period becomes billable again." onConfirm={() => run("cancel", "Invoice cancelled.")} onClose={() => setAction(null)} />}
      {action === "pay" && <PaymentForm invoice={inv} onClose={() => setAction(null)} onSaved={reload} />}
    </>
  );
}

const METHODS: PaymentMethod[] = ["bank_transfer", "upi", "card", "cash", "cheque", "other"];

function PaymentForm({ invoice, onClose, onSaved }: { invoice: Invoice; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ amount: invoice.amount_due, method: "bank_transfer", payment_date: today(), reference: "", note: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (Number(form.amount) <= 0) return setErrors({ amount: "Amount must be greater than zero." });
    if (Number(form.amount) > Number(invoice.amount_due)) return setErrors({ amount: `Cannot exceed the amount due (${money(invoice.amount_due)}).` });
    setBusy(true);
    setError(null);
    try {
      await api.post("/payments", { ...form, invoice_id: invoice.id, reference: form.reference || null, note: form.note || null });
      toast.success("Payment recorded.");
      onSaved();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setErrors(fieldErrors(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={`Record payment – ${invoice.number}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="muted">Amount due: {money(invoice.amount_due)}. Partial payments are allowed.</div>
        <div className="form-row">
          <Field label="Amount (₹)" error={errors.amount}><input type="number" min="0.01" step="0.01" required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
          <Field label="Method" error={errors.method}><select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>{METHODS.map((m) => <option key={m} value={m}>{label(m)}</option>)}</select></Field>
          <Field label="Payment date" error={errors.payment_date}><input type="date" max={today()} required value={form.payment_date} onChange={(e) => setForm({ ...form, payment_date: e.target.value })} /></Field>
        </div>
        <Field label="Reference" error={errors.reference}><input maxLength={120} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
        <Field label="Note" error={errors.note}><textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Record payment"}</button>
        </div>
      </form>
    </Modal>
  );
}
