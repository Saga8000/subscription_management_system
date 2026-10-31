import { useState, type FormEvent } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { Empty, ErrorAlert, Field, Loading, Modal, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useToast } from "../context/ToastContext";
import type { Plan } from "../types";
import { cadence, formatDate } from "../utils/format";

const FLAGS = [
  ["is_closable", "Customer can close early"],
  ["is_pausable", "Can be paused"],
  ["is_renewable", "Can be renewed"],
  ["auto_close", "Close automatically at end of term"],
  ["is_active", "Active"],
] as const;

export function PlansPage() {
  const { data, error, loading, reload } = useAsync(() => api.get<Plan[]>("/plans"), []);
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  return (
    <>
      <PageHeader title="Subscription plans" actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>New plan</button>} />
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.length === 0 ? <Empty>No plans yet.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Billing</th><th>Min qty</th><th>Term</th><th>Available</th><th>Options</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td><td>{cadence(p.billing_period, p.billing_interval)}</td><td>{p.min_quantity}</td>
                <td>{p.duration_periods ? `${p.duration_periods} period(s)` : "Open-ended"}</td>
                <td>{p.available_from || p.available_until ? `${formatDate(p.available_from)} – ${formatDate(p.available_until)}` : "Always"}</td>
                <td className="muted">{[p.is_closable && "closable", p.is_pausable && "pausable", p.is_renewable && "renewable", p.auto_close && "auto-close"].filter(Boolean).join(", ")}</td>
                <td><StatusBadge status={p.is_active ? "active" : "closed"} text={p.is_active ? "active" : "inactive"} /></td>
                <td><button className="btn btn-sm" onClick={() => setEditing(p)}>Edit</button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {editing && <PlanForm plan={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={reload} />}
    </>
  );
}

function PlanForm({ plan, onClose, onSaved }: { plan: Plan | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    name: plan?.name ?? "", billing_period: plan?.billing_period ?? "monthly", billing_interval: String(plan?.billing_interval ?? 1),
    min_quantity: String(plan?.min_quantity ?? 1), duration_periods: plan?.duration_periods ? String(plan.duration_periods) : "",
    available_from: plan?.available_from ?? "", available_until: plan?.available_until ?? "",
    is_closable: plan?.is_closable ?? true, is_pausable: plan?.is_pausable ?? true, is_renewable: plan?.is_renewable ?? true,
    auto_close: plan?.auto_close ?? true, is_active: plan?.is_active ?? true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      ...form, billing_interval: Number(form.billing_interval), min_quantity: Number(form.min_quantity),
      duration_periods: form.duration_periods ? Number(form.duration_periods) : null,
      available_from: form.available_from || null, available_until: form.available_until || null,
    };
    try {
      if (plan) await api.patch(`/plans/${plan.id}`, body);
      else await api.post("/plans", body);
      toast.success(plan ? "Plan updated." : "Plan created.");
      onSaved();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setErrors(fieldErrors(err));
    } finally {
      setBusy(false);
    }
  };
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <Modal title={plan ? "Edit plan" : "New plan"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <Field label="Name" error={errors.name}><input required value={form.name} onChange={set("name")} /></Field>
        <div className="form-row">
          <Field label="Billing period" error={errors.billing_period}>
            <select value={form.billing_period} onChange={set("billing_period")}>
              <option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option>
            </select>
          </Field>
          <Field label="Every N periods" error={errors.billing_interval}><input type="number" min={1} max={36} required value={form.billing_interval} onChange={set("billing_interval")} /></Field>
          <Field label="Minimum quantity" error={errors.min_quantity}><input type="number" min={1} required value={form.min_quantity} onChange={set("min_quantity")} /></Field>
        </div>
        <div className="form-row">
          <Field label="Term length (periods, blank = open-ended)" error={errors.duration_periods}><input type="number" min={1} value={form.duration_periods} onChange={set("duration_periods")} /></Field>
          <Field label="Available from" error={errors.available_from}><input type="date" value={form.available_from} onChange={set("available_from")} /></Field>
          <Field label="Available until" error={errors.available_until}><input type="date" value={form.available_until} onChange={set("available_until")} /></Field>
        </div>
        {FLAGS.map(([key, text]) => (
          <label className="check" key={key}><input type="checkbox" checked={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.checked })} /> {text}</label>
        ))}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Modal>
  );
}
