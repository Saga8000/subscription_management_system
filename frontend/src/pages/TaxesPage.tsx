import { useState, type FormEvent } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { Empty, ErrorAlert, Field, Loading, Modal, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Tax } from "../types";

export function TaxesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { data, error, loading, reload } = useAsync(() => api.get<Tax[]>("/taxes"), []);
  const [editing, setEditing] = useState<Tax | "new" | null>(null);
  return (
    <>
      <PageHeader title="Taxes" subtitle={isAdmin ? undefined : "Only administrators can change tax rules."}
        actions={isAdmin && <button className="btn btn-primary" onClick={() => setEditing("new")}>New tax</button>} />
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.length === 0 ? <Empty>No taxes configured.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th className="num">Rate</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((t) => (
              <tr key={t.id}><td>{t.name}</td><td className="num">{Number(t.rate_percent)}%</td>
                <td><StatusBadge status={t.is_active ? "active" : "closed"} text={t.is_active ? "active" : "inactive"} /></td>
                <td>{isAdmin && <button className="btn btn-sm" onClick={() => setEditing(t)}>Edit</button>}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {editing && <TaxForm tax={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={reload} />}
    </>
  );
}

function TaxForm({ tax, onClose, onSaved }: { tax: Tax | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ name: tax?.name ?? "", rate_percent: tax ? String(Number(tax.rate_percent)) : "", is_active: tax?.is_active ?? true });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (tax) await api.patch(`/taxes/${tax.id}`, form);
      else await api.post("/taxes", form);
      toast.success("Tax saved. Existing invoices keep their original tax snapshot.");
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
    <Modal title={tax ? "Edit tax" : "New tax"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <Field label="Name" error={errors.name}><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Rate (%)" error={errors.rate_percent}><input type="number" min="0" max="100" step="0.001" required value={form.rate_percent} onChange={(e) => setForm({ ...form, rate_percent: e.target.value })} /></Field>
        <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Save</button>
        </div>
      </form>
    </Modal>
  );
}
