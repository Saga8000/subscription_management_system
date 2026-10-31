import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ConfirmDialog, ErrorAlert, Loading, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useToast } from "../context/ToastContext";
import type { BillingRunResult, Dashboard } from "../types";
import { formatDate, label, money, today } from "../utils/format";

export function DashboardPage() {
  const toast = useToast();
  const [range, setRange] = useState({ period_start: today().slice(0, 8) + "01", period_end: today() });
  const { data, error, loading, reload } = useAsync(() => api.get<Dashboard>("/reports/dashboard", range), [range.period_start, range.period_end]);
  const [confirmRun, setConfirmRun] = useState(false);
  const [runResult, setRunResult] = useState<BillingRunResult | null>(null);

  const runBilling = async () => {
    const result = await api.post<BillingRunResult>("/billing/run", { as_of: today(), auto_confirm: false });
    setRunResult(result);
    toast.success(`Billing run complete: ${result.invoices_created.length} invoice(s) created.`);
    reload();
  };

  const max = Math.max(1, ...(data?.monthly ?? []).flatMap((m) => [Number(m.collected), Number(m.invoiced)]));

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Live figures from the database"
        actions={<button className="btn btn-primary" onClick={() => setConfirmRun(true)}>Run billing</button>}
      />
      <div className="filters">
        <label className="field">From<input type="date" value={range.period_start} onChange={(e) => setRange({ ...range, period_start: e.target.value })} /></label>
        <label className="field">To<input type="date" value={range.period_end} onChange={(e) => setRange({ ...range, period_end: e.target.value })} /></label>
      </div>
      {runResult && (
        <div className="alert alert-info">
          Checked {runResult.subscriptions_checked} subscription(s). Created: {runResult.invoices_created.join(", ") || "none"}.
          {runResult.subscriptions_closed.length > 0 && <> Closed: {runResult.subscriptions_closed.join(", ")}.</>}
          {runResult.failures.map((f) => <div key={f.subscription_id}>Failed {f.subscription_number}: {f.error}</div>)}
          {runResult.invoices_created.length > 0 && <div><Link to="/invoices?status=draft">Review draft invoices</Link></div>}
        </div>
      )}
      <ErrorAlert message={error} onRetry={reload} />
      {loading && !data ? <Loading /> : data && (
        <>
          <div className="grid">
            <Stat label="Active subscriptions" value={String(data.active_subscriptions)} />
            <Stat label="Revenue collected" value={money(data.revenue_collected)} hint="Payments received in period" />
            <Stat label="Amount invoiced" value={money(data.amount_invoiced)} hint="Confirmed invoices issued in period" />
            <Stat label="Outstanding balance" value={money(data.outstanding_balance)} hint="All unpaid confirmed invoices" />
            <Stat label="Overdue" value={`${money(data.overdue_amount)} (${data.overdue_count})`} hint={<Link to="/invoices?overdue=true">View overdue</Link>} />
            <Stat label="Monthly recurring revenue" value={money(data.monthly_recurring_revenue)} hint="Estimate, untaxed" />
          </div>
          <div className="grid" style={{ marginTop: 16 }}>
            <div className="card">
              <h2>Last 6 months</h2>
              <div className="bars">
                {data.monthly.map((m) => (
                  <div className="bar-group" key={m.month} title={`Collected ${money(m.collected)} / Invoiced ${money(m.invoiced)}`}>
                    <div className="bar-pair">
                      <div className="bar collected" style={{ height: `${(Number(m.collected) / max) * 100}%` }} />
                      <div className="bar invoiced" style={{ height: `${(Number(m.invoiced) / max) * 100}%` }} />
                    </div>
                    <span className="muted">{m.month.slice(5)}/{m.month.slice(2, 4)}</span>
                  </div>
                ))}
              </div>
              <div className="muted" style={{ marginTop: 8 }}><span className="badge">■ collected</span> <span className="badge" style={{ background: "#e0e7ff" }}>■ invoiced</span></div>
            </div>
            <div className="card">
              <h2>Subscriptions by status</h2>
              {data.subscription_status.length === 0 ? <div className="muted">No subscriptions yet.</div> :
                data.subscription_status.map((s) => <div key={s.status} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}><StatusBadge status={s.status} /> {s.count}</div>)}
              <h2 style={{ marginTop: 16 }}>Invoices by status</h2>
              {data.invoice_status.length === 0 ? <div className="muted">No invoices yet.</div> :
                data.invoice_status.map((s) => <div key={s.status} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}><StatusBadge status={s.status} /> {s.count} · {money(s.amount)}</div>)}
            </div>
          </div>
          <div className="card">
            <h2>Recent payments</h2>
            {data.recent_payments.length === 0 ? <div className="muted">No payments recorded yet.</div> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Method</th><th className="num">Amount</th></tr></thead>
                <tbody>{data.recent_payments.map((p) => (
                  <tr key={p.id}><td>{formatDate(p.payment_date)}</td><td><Link to={`/invoices/${p.invoice_id}`}>{p.invoice_number}</Link></td><td>{p.customer_name}</td><td>{label(p.method)}</td><td className="num">{money(p.amount)}</td></tr>
                ))}</tbody>
              </table></div>
            )}
          </div>
        </>
      )}
      {confirmRun && (
        <ConfirmDialog
          title="Run billing now?"
          message="Draft invoices will be generated for every active subscription whose next billing date is today or earlier. Periods that are already invoiced are skipped, so running it twice is safe."
          confirmLabel="Run billing"
          onConfirm={runBilling}
          onClose={() => setConfirmRun(false)}
        />
      )}
    </>
  );
}

function Stat({ label: text, value, hint }: { label: string; value: string; hint?: React.ReactNode }) {
  return (
    <div className="card stat" style={{ marginBottom: 0 }}>
      <div className="label">{text}</div>
      <div className="value">{value}</div>
      {hint && <div className="muted" style={{ marginTop: 4 }}>{hint}</div>}
    </div>
  );
}
