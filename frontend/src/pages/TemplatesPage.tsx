import { useState, type FormEvent } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { Empty, ErrorAlert, Field, Loading, Modal, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useToast } from "../context/ToastContext";
import type { Page, Plan, Product, QuotationTemplate } from "../types";

interface Line { product_id: string; variant_id: string; quantity: string; }

export function TemplatesPage() {
  const { data, error, loading, reload } = useAsync(() => api.get<QuotationTemplate[]>("/quotation-templates"), []);
  const plans = useAsync(() => api.get<Plan[]>("/plans"), []);
  const products = useAsync(() => api.get<Page<Product>>("/products", { page_size: 100 }), []);
  const [editing, setEditing] = useState<QuotationTemplate | "new" | null>(null);
  const planName = (id: number) => plans.data?.find((p) => p.id === id)?.name ?? `#${id}`;
  const productName = (id: number) => products.data?.items.find((p) => p.id === id)?.name ?? `#${id}`;
  return (
    <>
      <PageHeader title="Quotation templates" actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>New template</button>} />
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.length === 0 ? <Empty>No templates yet.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Plan</th><th>Validity</th><th>Lines</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((t) => (
              <tr key={t.id}><td>{t.name}</td><td>{planName(t.plan_id)}</td><td>{t.validity_days} days</td>
                <td>{t.lines.map((l) => `${productName(l.product_id)} × ${Number(l.quantity)}`).join(", ")}</td>
                <td><StatusBadge status={t.is_active ? "active" : "closed"} text={t.is_active ? "active" : "inactive"} /></td>
                <td><button className="btn btn-sm" onClick={() => setEditing(t)}>Edit</button></td></tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {editing && <TemplateForm template={editing === "new" ? null : editing} plans={plans.data ?? []} products={products.data?.items ?? []} onClose={() => setEditing(null)} onSaved={reload} />}
    </>
  );
}

function TemplateForm({ template, plans, products, onClose, onSaved }: { template: QuotationTemplate | null; plans: Plan[]; products: Product[]; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ name: template?.name ?? "", plan_id: template ? String(template.plan_id) : "", validity_days: String(template?.validity_days ?? 30), notes: template?.notes ?? "", is_active: template?.is_active ?? true });
  const [lines, setLines] = useState<Line[]>(template?.lines.map((l) => ({ product_id: String(l.product_id), variant_id: l.variant_id ? String(l.variant_id) : "", quantity: String(Number(l.quantity)) })) ?? [{ product_id: "", variant_id: "", quantity: "1" }]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (lines.some((l) => !l.product_id)) return setError("Every line needs a product.");
    setBusy(true);
    setError(null);
    const body = { ...form, plan_id: Number(form.plan_id), validity_days: Number(form.validity_days), notes: form.notes || null,
      lines: lines.map((l) => ({ product_id: Number(l.product_id), variant_id: l.variant_id ? Number(l.variant_id) : null, quantity: l.quantity })) };
    try {
      if (template) await api.patch(`/quotation-templates/${template.id}`, body);
      else await api.post("/quotation-templates", body);
      toast.success("Template saved.");
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
    <Modal title={template ? "Edit template" : "New template"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="form-row">
          <Field label="Name" error={errors.name}><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Plan" error={errors.plan_id}><select required value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}><option value="">Select…</option>{plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
          <Field label="Validity (days)" error={errors.validity_days}><input type="number" min={1} max={365} value={form.validity_days} onChange={(e) => setForm({ ...form, validity_days: e.target.value })} /></Field>
        </div>
        {lines.map((l, i) => {
          const p = products.find((x) => String(x.id) === l.product_id);
          return (
            <div className="form-row" key={i} style={{ alignItems: "end" }}>
              <Field label="Product" error={errors[`lines.${i}.product_id`]}><select value={l.product_id} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, product_id: e.target.value, variant_id: "" } : x)))}><option value="">Select…</option>{products.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
              <Field label="Variant"><select value={l.variant_id} disabled={!p?.variants.length} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, variant_id: e.target.value } : x)))}><option value="">Base</option>{p?.variants.filter((v) => v.is_active).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></Field>
              <Field label="Quantity" error={errors[`lines.${i}.quantity`]}><input type="number" min={1} value={l.quantity} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} /></Field>
              <button type="button" className="btn btn-danger" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</button>
            </div>
          );
        })}
        <div><button type="button" className="btn" onClick={() => setLines([...lines, { product_id: "", variant_id: "", quantity: "1" }])}>Add line</button></div>
        <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Save</button>
        </div>
      </form>
    </Modal>
  );
}
