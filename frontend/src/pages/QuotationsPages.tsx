import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorMessage, fieldErrors } from "../api/client";
import { ConfirmDialog, Empty, ErrorAlert, Field, Loading, PageHeader, Pagination, StatusBadge, useAsync } from "../components/ui";
import { isInternal, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Customer, LineOut, Page, Plan, Product, Quotation, QuotationListItem, QuotationTemplate, Tax } from "../types";
import { formatDate, money, quotationStatusLabel, today } from "../utils/format";

export function QuotationsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(
    () => api.get<Page<QuotationListItem>>("/quotations", { status, page, customer_id: params.get("customer_id") }),
    [status, page, params.get("customer_id")],
  );
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="Quotations" actions={isInternal(user) && <Link className="btn btn-primary" to="/quotations/new">New quotation</Link>} />
      <div className="filters">
        <select value={status} onChange={(e) => { setParams(e.target.value ? { status: e.target.value } : {}); setPage(1); }}>
          <option value="">All statuses</option>
          {isInternal(user) && <option value="draft">Draft</option>}
          <option value="sent">Sent</option><option value="confirmed">Confirmed</option><option value="cancelled">Cancelled</option>
        </select>
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No quotations found.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Number</th><th>Customer</th><th>Plan</th><th>Start</th><th>Expires</th><th>Status</th></tr></thead>
            <tbody>{data.items.map((q) => (
              <tr key={q.id} className="clickable" onClick={() => navigate(`/quotations/${q.id}`)}>
                <td><Link to={`/quotations/${q.id}`}>{q.number}</Link></td><td>{q.customer_name}</td><td>{q.plan_name}</td>
                <td>{formatDate(q.start_date)}</td><td>{formatDate(q.expiration_date)}</td>
                <td>{q.is_expired ? <StatusBadge status="expired" /> : <StatusBadge status={q.status} text={quotationStatusLabel(q.status)} />}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <Pagination page={data} onPage={setPage} />
      </div>
    </>
  );
}

export function LinesTable({ lines, untaxed, tax, total }: { lines: LineOut[]; untaxed: string; tax: string; total: string }) {
  return (
    <>
      <div className="table-wrap"><table>
        <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Unit price</th><th className="num">Tax</th><th className="num">Subtotal</th><th className="num">Total</th></tr></thead>
        <tbody>{lines.map((l) => (
          <tr key={l.id}><td>{l.description}</td><td className="num">{Number(l.quantity)}</td><td className="num">{money(l.unit_price)}</td>
            <td className="num">{Number(l.tax_rate)}%</td><td className="num">{money(l.subtotal)}</td><td className="num">{money(l.total)}</td></tr>
        ))}</tbody>
      </table></div>
      <div className="totals" style={{ marginTop: 12 }}>
        <div><span>Untaxed</span><span>{money(untaxed)}</span></div>
        <div><span>Tax</span><span>{money(tax)}</span></div>
        <div className="grand"><span>Total per period</span><span>{money(total)}</span></div>
      </div>
    </>
  );
}

export function QuotationDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { data: q, error, loading, reload, setData } = useAsync(() => api.get<Quotation>(`/quotations/${id}`), [id]);
  const [action, setAction] = useState<"send" | "confirm" | "cancel" | null>(null);
  if (loading && !q) return <Loading />;
  if (!q) return <ErrorAlert message={error} onRetry={reload} />;
  const internal = isInternal(user);
  const run = async (name: string, success: string) => {
    const updated = await api.post<Quotation>(`/quotations/${q.id}/${name}`);
    setData(updated);
    toast.success(success);
  };
  const canAct = !q.is_expired;
  return (
    <>
      <PageHeader
        title={`Quotation ${q.number}`}
        subtitle={<>{q.customer_name} · {q.plan_name} {q.is_expired ? <StatusBadge status="expired" /> : <StatusBadge status={q.status} text={quotationStatusLabel(q.status)} />}</>}
        actions={<>
          {internal && q.status === "draft" && <Link className="btn" to={`/quotations/${q.id}/edit`}>Edit</Link>}
          {internal && q.status === "draft" && canAct && <button className="btn btn-primary" onClick={() => setAction("send")}>Send to customer</button>}
          {q.status === "sent" && canAct && <button className="btn btn-primary" onClick={() => setAction("confirm")}>{internal ? "Confirm" : "Accept quotation"}</button>}
          {(q.status === "sent" || (internal && q.status === "draft")) && <button className="btn btn-danger" onClick={() => setAction("cancel")}>{internal ? "Cancel" : "Decline"}</button>}
          {q.subscription_id && <Link className="btn" to={`/subscriptions/${q.subscription_id}`}>View subscription</Link>}
        </>}
      />
      <ErrorAlert message={error} />
      {q.is_expired && <div className="alert alert-error">This quotation expired on {formatDate(q.expiration_date)}.{internal && q.status === "draft" && " Edit it to extend the expiration date."}</div>}
      <div className="card">
        <dl className="details">
          <dt>Quotation date</dt><dd>{formatDate(q.quotation_date)}</dd>
          <dt>Expires</dt><dd>{formatDate(q.expiration_date)}</dd>
          <dt>Subscription start</dt><dd>{formatDate(q.start_date)}</dd>
          <dt>Payment terms</dt><dd>{q.payment_terms_days} days</dd>
          {q.notes && <><dt>Notes</dt><dd>{q.notes}</dd></>}
        </dl>
      </div>
      <div className="card"><LinesTable lines={q.lines} untaxed={q.untaxed_amount} tax={q.tax_total} total={q.total} /></div>
      {action === "send" && <ConfirmDialog title="Send quotation?" message="The customer will be able to see and accept it in their portal." onConfirm={() => run("send", "Quotation sent.")} onClose={() => setAction(null)} />}
      {action === "confirm" && <ConfirmDialog title={internal ? "Confirm quotation?" : "Accept quotation?"} message={`A subscription starting ${formatDate(q.start_date)} will be created at ${money(q.total)} per billing period.`} onConfirm={async () => { await run("confirm", "Quotation confirmed – subscription created."); reload(); }} onClose={() => setAction(null)} />}
      {action === "cancel" && <ConfirmDialog danger title={internal ? "Cancel quotation?" : "Decline quotation?"} message="This cannot be undone." confirmLabel={internal ? "Cancel quotation" : "Decline"} onConfirm={() => run("cancel", "Quotation cancelled.")} onClose={() => setAction(null)} />}
      {!internal && <button className="btn" onClick={() => navigate("/quotations")}>Back to quotations</button>}
    </>
  );
}

interface LineForm { product_id: string; variant_id: string; quantity: string; tax_id: string; }
const emptyLine: LineForm = { product_id: "", variant_id: "", quantity: "1", tax_id: "default" };

export function QuotationFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const customers = useAsync(() => api.get<Page<Customer>>("/customers", { page_size: 100, active: true }), []);
  const plans = useAsync(() => api.get<Plan[]>("/plans", { active_only: true }), []);
  const products = useAsync(() => api.get<Page<Product>>("/products", { page_size: 100, active: true }), []);
  const taxes = useAsync(() => api.get<Tax[]>("/taxes"), []);
  const templates = useAsync(() => api.get<QuotationTemplate[]>("/quotation-templates"), []);
  const [form, setForm] = useState({ customer_id: "", plan_id: "", template_id: "", start_date: today(), expiration_date: "", payment_terms_days: "15", notes: "" });
  const [lines, setLines] = useState<LineForm[]>([{ ...emptyLine }]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.get<Quotation>(`/quotations/${id}`).then((q) => {
      setForm({ customer_id: String(q.customer_id), plan_id: String(q.plan_id), template_id: "", start_date: q.start_date, expiration_date: q.expiration_date, payment_terms_days: String(q.payment_terms_days), notes: q.notes ?? "" });
      setLines(q.lines.map((l) => ({ product_id: String(l.product_id), variant_id: l.variant_id ? String(l.variant_id) : "", quantity: String(Number(l.quantity)), tax_id: l.tax_id ? String(l.tax_id) : "none" })));
    }).catch((e) => setError(errorMessage(e)));
  }, [id]);

  const applyTemplate = (templateId: string) => {
    const t = templates.data?.find((x) => String(x.id) === templateId);
    setForm({ ...form, template_id: templateId, plan_id: t ? String(t.plan_id) : form.plan_id });
    if (t) setLines(t.lines.map((l) => ({ product_id: String(l.product_id), variant_id: l.variant_id ? String(l.variant_id) : "", quantity: String(Number(l.quantity)), tax_id: "default" })));
  };
  const productById = (pid: string) => products.data?.items.find((p) => String(p.id) === pid);
  const unitPrice = (l: LineForm) => {
    const p = productById(l.product_id);
    if (!p) return 0;
    const v = p.variants.find((x) => String(x.id) === l.variant_id);
    return Number(v ? v.unit_price : p.sales_price);
  };
  const estimate = lines.reduce((sum, l) => sum + unitPrice(l) * Number(l.quantity || 0), 0);
  const plan = plans.data?.find((p) => String(p.id) === form.plan_id);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (lines.some((l) => !l.product_id)) return setError("Every line needs a product.");
    setBusy(true);
    setError(null);
    const body = {
      ...(id ? {} : { customer_id: Number(form.customer_id), template_id: form.template_id ? Number(form.template_id) : null }),
      plan_id: Number(form.plan_id), start_date: form.start_date, expiration_date: form.expiration_date || null,
      payment_terms_days: Number(form.payment_terms_days), notes: form.notes || null,
      lines: lines.map((l) => ({
        product_id: Number(l.product_id), variant_id: l.variant_id ? Number(l.variant_id) : null, quantity: l.quantity,
        tax_id: l.tax_id !== "default" && l.tax_id !== "none" ? Number(l.tax_id) : null, no_tax: l.tax_id === "none",
      })),
    };
    try {
      const q = id ? await api.patch<Quotation>(`/quotations/${id}`, body) : await api.post<Quotation>("/quotations", body);
      toast.success(id ? "Quotation updated." : `Quotation ${q.number} created as draft.`);
      navigate(`/quotations/${q.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setErrors(fieldErrors(err));
    } finally {
      setBusy(false);
    }
  };

  if (customers.loading || plans.loading || products.loading) return <Loading />;
  return (
    <>
      <PageHeader title={id ? "Edit quotation" : "New quotation"} />
      <form className="card form" onSubmit={submit}>
        <ErrorAlert message={error ?? customers.error ?? plans.error ?? products.error} />
        <div className="form-row">
          <Field label="Customer" error={errors.customer_id}>
            <select required disabled={!!id} value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
              <option value="">Select customer…</option>
              {customers.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.email})</option>)}
            </select>
          </Field>
          {!id && <Field label="Template (optional)" error={errors.template_id}>
            <select value={form.template_id} onChange={(e) => applyTemplate(e.target.value)}>
              <option value="">None</option>
              {templates.data?.filter((t) => t.is_active).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </Field>}
          <Field label="Plan" error={errors.plan_id}>
            <select required value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}>
              <option value="">Select plan…</option>
              {plans.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field label="Start date" error={errors.start_date}><input type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
          <Field label="Expires (blank = default validity)" error={errors.expiration_date}><input type="date" value={form.expiration_date} onChange={(e) => setForm({ ...form, expiration_date: e.target.value })} /></Field>
          <Field label="Payment terms (days)" error={errors.payment_terms_days}><input type="number" min={0} max={365} required value={form.payment_terms_days} onChange={(e) => setForm({ ...form, payment_terms_days: e.target.value })} /></Field>
        </div>
        <h2>Lines {plan && <span className="muted">(minimum quantity {plan.min_quantity})</span>}</h2>
        {lines.map((l, i) => {
          const p = productById(l.product_id);
          return (
            <div className="form-row" key={i} style={{ alignItems: "end" }}>
              <Field label="Product" error={errors[`lines.${i}.product_id`]}>
                <select value={l.product_id} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, product_id: e.target.value, variant_id: "" } : x)))}>
                  <option value="">Select…</option>
                  {products.data?.items.map((pr) => <option key={pr.id} value={pr.id}>{pr.name} – {money(pr.sales_price)}</option>)}
                </select>
              </Field>
              <Field label="Variant" error={errors[`lines.${i}.variant_id`]}>
                <select value={l.variant_id} disabled={!p?.variants.length} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, variant_id: e.target.value } : x)))}>
                  <option value="">Base</option>
                  {p?.variants.filter((v) => v.is_active).map((v) => <option key={v.id} value={v.id}>{v.name} – {money(v.unit_price)}</option>)}
                </select>
              </Field>
              <Field label="Quantity" error={errors[`lines.${i}.quantity`]}><input type="number" min={plan?.min_quantity ?? 1} step="1" value={l.quantity} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} /></Field>
              <Field label="Tax" error={errors[`lines.${i}.tax_id`]}>
                <select value={l.tax_id} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, tax_id: e.target.value } : x)))}>
                  <option value="default">Product default</option><option value="none">No tax</option>
                  {taxes.data?.filter((t) => t.is_active).map((t) => <option key={t.id} value={t.id}>{t.name} ({Number(t.rate_percent)}%)</option>)}
                </select>
              </Field>
              <button type="button" className="btn btn-danger" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</button>
            </div>
          );
        })}
        <div><button type="button" className="btn" onClick={() => setLines([...lines, { ...emptyLine }])}>Add line</button></div>
        <div className="muted">Estimated untaxed amount per period: <strong>{money(estimate)}</strong> (final totals, taxes and discounts are calculated by the server).</div>
        <Field label="Notes" error={errors.notes}><textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={() => navigate(-1)}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save draft"}</button>
        </div>
      </form>
    </>
  );
}
