import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Empty, ErrorAlert, Loading, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import type { InvoiceListItem, Page, QuotationListItem, SubscriptionListItem } from "../types";
import { formatDate, money } from "../utils/format";
import { InvoiceTable } from "./InvoicesPages";

export function PortalPage() {
  const { user } = useAuth();
  const subs = useAsync(() => api.get<Page<SubscriptionListItem>>("/subscriptions", { page_size: 50 }), []);
  const unpaid = useAsync(() => api.get<Page<InvoiceListItem>>("/invoices", { status: "confirmed", page_size: 50 }), []);
  const quotes = useAsync(() => api.get<Page<QuotationListItem>>("/quotations", { status: "sent", page_size: 20 }), []);
  const due = (unpaid.data?.items ?? []).reduce((s, i) => s + Number(i.amount_due), 0);
  const overdue = (unpaid.data?.items ?? []).filter((i) => i.is_overdue).length;

  return (
    <>
      <PageHeader title={`Welcome, ${user?.full_name}`} subtitle="Your subscriptions, quotations and invoices" />
      <div className="grid">
        <div className="card stat"><div className="label">Active subscriptions</div><div className="value">{subs.data?.items.filter((s) => s.status === "active").length ?? "…"}</div></div>
        <div className="card stat"><div className="label">Balance due</div><div className="value">{unpaid.data ? money(due) : "…"}</div>{overdue > 0 && <div className="field-error">{overdue} overdue invoice(s)</div>}</div>
        <div className="card stat"><div className="label">Quotations awaiting you</div><div className="value">{quotes.data?.total ?? "…"}</div></div>
      </div>
      {quotes.data && quotes.data.items.length > 0 && (
        <div className="card">
          <h2>Quotations awaiting your response</h2>
          {quotes.data.items.map((q) => (
            <div key={q.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <span><Link to={`/quotations/${q.id}`}>{q.number}</Link> · {q.plan_name} · starts {formatDate(q.start_date)}</span>
              {q.is_expired ? <StatusBadge status="expired" /> : <Link className="btn btn-sm btn-primary" to={`/quotations/${q.id}`}>Review</Link>}
            </div>
          ))}
        </div>
      )}
      <div className="card">
        <h2>Unpaid invoices</h2>
        <ErrorAlert message={unpaid.error} onRetry={unpaid.reload} />
        {unpaid.loading ? <Loading /> : unpaid.data && (unpaid.data.items.length ? <InvoiceTable items={unpaid.data.items} /> : <Empty>You're all paid up.</Empty>)}
      </div>
      <div className="card">
        <h2>My subscriptions</h2>
        <ErrorAlert message={subs.error} onRetry={subs.reload} />
        {subs.loading ? <Loading /> : subs.data && (subs.data.items.length === 0 ? <Empty>No subscriptions yet.</Empty> : (
          <div className="table-wrap"><table><thead><tr><th>Number</th><th>Plan</th><th>Next invoice</th><th className="num">Per period</th><th>Status</th></tr></thead>
            <tbody>{subs.data.items.map((s) => (
              <tr key={s.id}><td><Link to={`/subscriptions/${s.id}`}>{s.number}</Link></td><td>{s.plan_name}</td>
                <td>{s.status === "closed" ? "—" : formatDate(s.next_invoice_date)}</td><td className="num">{money(s.recurring_total)}</td><td><StatusBadge status={s.status} /></td></tr>
            ))}</tbody></table></div>
        ))}
      </div>
    </>
  );
}
