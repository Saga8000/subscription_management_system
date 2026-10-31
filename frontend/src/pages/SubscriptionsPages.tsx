import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { ConfirmDialog, Empty, ErrorAlert, Field, Loading, PageHeader, Pagination, StatusBadge, useAsync } from "../components/ui";
import { isInternal, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Invoice, InvoiceListItem, Page, Quotation, Subscription, SubscriptionListItem } from "../types";
import { cadence, formatDate, money, today } from "../utils/format";
import { LinesTable } from "./QuotationsPages";
import { InvoiceTable } from "./InvoicesPages";

export function SubscriptionsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const customerId = params.get("customer_id");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsync(
    () => api.get<Page<SubscriptionListItem>>("/subscriptions", { status, q, page, customer_id: customerId }),
    [status, q, page, customerId],
  );
  return (
    <>
      <PageHeader title="Subscriptions" subtitle={customerId ? <>Filtered by customer · <Link to="/subscriptions">clear</Link></> : undefined} />
      <div className="filters">
        <select value={status} onChange={(e) => { setParams(e.target.value ? { status: e.target.value } : {}); setPage(1); }}>
          <option value="">All statuses</option><option value="confirmed">Confirmed</option><option value="active">Active</option>
          <option value="paused">Paused</option><option value="closed">Closed</option>
        </select>
        <input placeholder="Search number" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No subscriptions found.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Number</th><th>Customer</th><th>Plan</th><th>Start</th><th>Next invoice</th><th>Ends</th><th className="num">Per period</th><th>Status</th></tr></thead>
            <tbody>{data.items.map((s) => (
              <tr key={s.id} className="clickable" onClick={() => navigate(`/subscriptions/${s.id}`)}>
                <td><Link to={`/subscriptions/${s.id}`}>{s.number}</Link></td><td>{s.customer_name}</td><td>{s.plan_name}</td>
                <td>{formatDate(s.start_date)}</td><td>{s.status === "closed" ? "—" : formatDate(s.next_invoice_date)}</td>
                <td>{formatDate(s.expiry_date)}</td><td className="num">{money(s.recurring_total)}</td><td><StatusBadge status={s.status} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <Pagination page={data} onPage={setPage} />
      </div>
    </>
  );
}

type Action = "activate" | "pause" | "resume" | "close" | "renew" | "generate";

export function SubscriptionDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { data: s, error, loading, reload, setData } = useAsync(() => api.get<Subscription>(`/subscriptions/${id}`), [id]);
  const invoices = useAsync(() => api.get<Page<InvoiceListItem>>("/invoices", { subscription_id: id, page_size: 50 }), [id]);
  const [action, setAction] = useState<Action | null>(null);
  const [reason, setReason] = useState("");
  if (loading && !s) return <Loading />;
  if (!s) return <ErrorAlert message={error} onRetry={reload} />;
  const internal = isInternal(user);
  const lifecycle = async (name: string, message: string, body: unknown = {}) => {
    setData(await api.post<Subscription>(`/subscriptions/${s.id}/${name}`, body));
    toast.success(message);
  };
  const open = s.status !== "closed";
  return (
    <>
      <PageHeader
        title={`Subscription ${s.number}`}
        subtitle={<>{s.customer_name} · {s.plan_name} · {cadence(s.billing_period, s.billing_interval)} <StatusBadge status={s.status} /></>}
        actions={<>
          {internal && s.status === "confirmed" && <button className="btn btn-primary" onClick={() => setAction("activate")}>Activate</button>}
          {internal && s.status === "active" && <button className="btn btn-primary" onClick={() => setAction("generate")}>Generate invoice</button>}
          {internal && s.status === "active" && s.is_pausable && <button className="btn" onClick={() => setAction("pause")}>Pause</button>}
          {internal && s.status === "paused" && <button className="btn btn-primary" onClick={() => setAction("resume")}>Resume</button>}
          {internal && s.is_renewable && (s.status === "active" || s.status === "closed") && <button className="btn" onClick={() => setAction("renew")}>Renew</button>}
          {open && (internal || s.is_closable) && <button className="btn btn-danger" onClick={() => setAction("close")}>Close</button>}
        </>}
      />
      <ErrorAlert message={error} />
      <div className="card">
        <dl className="details">
          <dt>Quotation</dt><dd><Link to={`/quotations/${s.quotation_id}`}>{s.quotation_number}</Link></dd>
          <dt>Start date</dt><dd>{formatDate(s.start_date)}</dd>
          <dt>Ends</dt><dd>{s.expiry_date ? formatDate(s.expiry_date) : "Open-ended"}</dd>
          <dt>Next invoice</dt><dd>{open ? formatDate(s.next_invoice_date) : "—"}</dd>
          <dt>Payment terms</dt><dd>{s.payment_terms_days} days</dd>
          {s.close_reason && <><dt>Closed</dt><dd>{s.close_reason}</dd></>}
        </dl>
      </div>
      <div className="card"><LinesTable lines={s.lines} untaxed={s.untaxed_amount} tax={s.tax_total} total={s.recurring_total} /></div>
      <div className="card">
        <h2>Invoices</h2>
        <ErrorAlert message={invoices.error} onRetry={invoices.reload} />
        {invoices.data && (invoices.data.items.length ? <InvoiceTable items={invoices.data.items} /> : <Empty>No invoices yet.</Empty>)}
      </div>
      {action === "activate" && <ConfirmDialog title="Activate subscription?" message="It will be included in billing runs from its next invoice date." onConfirm={() => lifecycle("activate", "Subscription activated.")} onClose={() => setAction(null)} />}
      {action === "pause" && <ConfirmDialog title="Pause subscription?" message="No invoices are generated while paused. Periods that start while paused are not billed." onConfirm={() => lifecycle("pause", "Subscription paused.")} onClose={() => setAction(null)} />}
      {action === "resume" && <ConfirmDialog title="Resume subscription?" message="Billing restarts from the next period start date." onConfirm={() => lifecycle("resume", "Subscription resumed.")} onClose={() => setAction(null)} />}
      {action === "close" && (
        <ConfirmDialog danger title="Close subscription?" confirmLabel="Close subscription" message="No further invoices will be generated. Existing invoices stay payable." onConfirm={() => lifecycle("close", "Subscription closed.", { reason: reason || null })} onClose={() => setAction(null)}>
          <Field label="Reason (optional)"><input maxLength={255} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        </ConfirmDialog>
      )}
      {action === "renew" && <ConfirmDialog title="Create renewal quotation?" message="A draft quotation with the same lines and prices will be created for review." onConfirm={async () => { const q = await api.post<Quotation>(`/subscriptions/${s.id}/renew`); toast.success(`Renewal quotation ${q.number} created.`); navigate(`/quotations/${q.id}`); }} onClose={() => setAction(null)} />}
      {action === "generate" && <ConfirmDialog title="Generate invoice now?" message={`Draft invoices are created for every unbilled period up to today (${formatDate(today())}). Already-invoiced periods are skipped.`} onConfirm={async () => { const created = await api.post<Invoice[]>(`/subscriptions/${s.id}/generate-invoice`, {}); toast.success(`Created ${created.map((i) => i.number).join(", ")}.`); reload(); invoices.reload(); }} onClose={() => setAction(null)} />}
    </>
  );
}
