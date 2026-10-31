import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Empty, ErrorAlert, Loading, PageHeader, Pagination, useAsync } from "../components/ui";
import type { Page, PaymentListItem } from "../types";
import { formatDate, label, money } from "../utils/format";

export function PaymentsPage() {
  const [range, setRange] = useState({ date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(() => api.get<Page<PaymentListItem>>("/payments", { ...range, page }), [range.date_from, range.date_to, page]);
  return (
    <>
      <PageHeader title="Payments" subtitle="Payments are recorded from an invoice's detail page." />
      <div className="filters">
        <label className="field">From<input type="date" value={range.date_from} onChange={(e) => { setRange({ ...range, date_from: e.target.value }); setPage(1); }} /></label>
        <label className="field">To<input type="date" value={range.date_to} onChange={(e) => { setRange({ ...range, date_to: e.target.value }); setPage(1); }} /></label>
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No payments found.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Method</th><th>Reference</th><th className="num">Amount</th></tr></thead>
            <tbody>{data.items.map((p) => (
              <tr key={p.id}><td>{formatDate(p.payment_date)}</td><td><Link to={`/invoices/${p.invoice_id}`}>{p.invoice_number}</Link></td>
                <td>{p.customer_name}</td><td>{label(p.method)}</td><td>{p.reference ?? "—"}</td><td className="num">{money(p.amount)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
        <Pagination page={data} onPage={setPage} />
      </div>
    </>
  );
}
