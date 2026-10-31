import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage, fieldErrors } from "../api/client";
import { passwordProblems } from "./AuthPages";
import { Empty, ErrorAlert, Field, Loading, Modal, PageHeader, Pagination, StatusBadge, useAsync } from "../components/ui";
import { useToast } from "../context/ToastContext";
import type { Customer, Page } from "../types";

export function CustomersPage() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(() => api.get<Page<Customer>>("/customers", { q, page }), [q, page]);
  const [editing, setEditing] = useState<Customer | "new" | null>(null);
  const [portalFor, setPortalFor] = useState<Customer | null>(null);

  return (
    <>
      <PageHeader title="Customers" actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>New customer</button>} />
      <div className="filters">
        <input placeholder="Search name or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No customers found.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Portal</th><th>Status</th><th /></tr></thead>
            <tbody>{data.items.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td><td>{c.email}</td><td>{c.phone ?? "—"}</td>
                <td>{c.user_id ? "Enabled" : <button className="link-btn" onClick={() => setPortalFor(c)}>Enable</button>}</td>
                <td><StatusBadge status={c.is_active ? "active" : "closed"} text={c.is_active ? "active" : "inactive"} /></td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-sm" onClick={() => setEditing(c)}>Edit</button>
                  <Link className="btn btn-sm" to={`/subscriptions?customer_id=${c.id}`}>Subscriptions</Link>
                  <Link className="btn btn-sm" to={`/invoices?customer_id=${c.id}`}>Invoices</Link>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <Pagination page={data} onPage={setPage} />
      </div>
      {editing && <CustomerForm customer={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={reload} />}
      {portalFor && <PortalAccessForm customer={portalFor} onClose={() => setPortalFor(null)} onSaved={reload} />}
    </>
  );
}

function CustomerForm({ customer, onClose, onSaved }: { customer: Customer | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    name: customer?.name ?? "", email: customer?.email ?? "", phone: customer?.phone ?? "",
    address: customer?.address ?? "", is_active: customer?.is_active ?? true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = { name: form.name, email: form.email, phone: form.phone || null, address: form.address || null };
    try {
      if (customer) await api.patch(`/customers/${customer.id}`, { ...body, is_active: form.is_active });
      else await api.post("/customers", body);
      toast.success(customer ? "Customer updated." : "Customer created.");
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
    <Modal title={customer ? "Edit customer" : "New customer"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="form-row">
          <Field label="Name" error={errors.name}><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Email" error={errors.email}><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        </div>
        <Field label="Phone" error={errors.phone}><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        <Field label="Address" error={errors.address}><textarea rows={3} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
        {customer && <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Modal>
  );
}

function PortalAccessForm({ customer, onClose, onSaved }: { customer: Customer; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblems(password);
    if (problems.length) return setError(`Password needs ${problems.join(", ")}.`);
    setBusy(true);
    try {
      await api.post(`/customers/${customer.id}/portal-access`, { password });
      toast.success(`Portal access enabled for ${customer.email}.`);
      onSaved();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={`Enable portal access – ${customer.name}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="muted">The customer signs in with {customer.email} and this initial password.</div>
        <Field label="Initial password"><input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Enable</button>
        </div>
      </form>
    </Modal>
  );
}
