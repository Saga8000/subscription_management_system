import { useState, type FormEvent } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { Empty, ErrorAlert, Field, Loading, Modal, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Discount, Page, Product } from "../types";
import { formatDate, money } from "../utils/format";

export function DiscountsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { data, error, loading, reload } = useAsync(() => api.get<Discount[]>("/discounts"), []);
  const products = useAsync(() => api.get<Page<Product>>("/products", { page_size: 100 }), []);
  const [editing, setEditing] = useState<Discount | "new" | null>(null);
  return (
    <>
      <PageHeader title="Discounts" subtitle={isAdmin ? "The single best applicable discount is applied automatically at invoice time." : "Only administrators can change discount rules."}
        actions={isAdmin && <button className="btn btn-primary" onClick={() => setEditing("new")}>New discount</button>} />
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.length === 0 ? <Empty>No discounts configured.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Value</th><th>Conditions</th><th>Valid</th><th>Usage</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td><td>{d.discount_type === "percentage" ? `${Number(d.value)}%` : money(d.value)}</td>
                <td className="muted">{[d.min_purchase_amount && `min ${money(d.min_purchase_amount)}`, d.min_quantity && `min qty ${Number(d.min_quantity)}`, d.product_ids.length && `${d.product_ids.length} product(s)`, d.subscription_ids.length && `${d.subscription_ids.length} subscription(s)`].filter(Boolean).join(", ") || "All"}</td>
                <td>{d.valid_from || d.valid_until ? `${formatDate(d.valid_from)} – ${formatDate(d.valid_until)}` : "Always"}</td>
                <td>{d.usage_count}{d.usage_limit ? ` / ${d.usage_limit}` : ""}</td>
                <td><StatusBadge status={d.is_active ? "active" : "closed"} text={d.is_active ? "active" : "inactive"} /></td>
                <td>{isAdmin && <button className="btn btn-sm" onClick={() => setEditing(d)}>Edit</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {editing && <DiscountForm discount={editing === "new" ? null : editing} products={products.data?.items ?? []} onClose={() => setEditing(null)} onSaved={reload} />}
    </>
  );
}

function DiscountForm({ discount, products, onClose, onSaved }: { discount: Discount | null; products: Product[]; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    name: discount?.name ?? "", discount_type: discount?.discount_type ?? "percentage", value: discount?.value ?? "",
    min_purchase_amount: discount?.min_purchase_amount ?? "", min_quantity: discount?.min_quantity ?? "",
    valid_from: discount?.valid_from ?? "", valid_until: discount?.valid_until ?? "",
    usage_limit: discount?.usage_limit ? String(discount.usage_limit) : "", is_active: discount?.is_active ?? true,
  });
  const [productIds, setProductIds] = useState<number[]>(discount?.product_ids ?? []);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (form.discount_type === "percentage" && Number(form.value) > 100) return setErrors({ value: "A percentage cannot exceed 100." });
    setBusy(true);
    setError(null);
    const body = {
      ...form, min_purchase_amount: form.min_purchase_amount || null, min_quantity: form.min_quantity || null,
      valid_from: form.valid_from || null, valid_until: form.valid_until || null,
      usage_limit: form.usage_limit ? Number(form.usage_limit) : null, product_ids: productIds,
      subscription_ids: discount?.subscription_ids ?? [],
    };
    try {
      if (discount) await api.put(`/discounts/${discount.id}`, body);
      else await api.post("/discounts", body);
      toast.success("Discount saved.");
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
    <Modal title={discount ? "Edit discount" : "New discount"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="form-row">
          <Field label="Name" error={errors.name}><input required value={form.name} onChange={set("name")} /></Field>
          <Field label="Type" error={errors.discount_type}><select value={form.discount_type} onChange={set("discount_type")}><option value="percentage">Percentage</option><option value="fixed">Fixed amount</option></select></Field>
          <Field label={form.discount_type === "percentage" ? "Value (%)" : "Value (₹)"} error={errors.value}><input type="number" min="0.01" step="0.01" required value={form.value} onChange={set("value")} /></Field>
        </div>
        <div className="form-row">
          <Field label="Minimum purchase (₹)" error={errors.min_purchase_amount}><input type="number" min="0" step="0.01" value={form.min_purchase_amount} onChange={set("min_purchase_amount")} /></Field>
          <Field label="Minimum quantity" error={errors.min_quantity}><input type="number" min="0" step="1" value={form.min_quantity} onChange={set("min_quantity")} /></Field>
          <Field label="Usage limit" error={errors.usage_limit}><input type="number" min="1" value={form.usage_limit} onChange={set("usage_limit")} /></Field>
        </div>
        <div className="form-row">
          <Field label="Valid from" error={errors.valid_from}><input type="date" value={form.valid_from} onChange={set("valid_from")} /></Field>
          <Field label="Valid until" error={errors.valid_until}><input type="date" value={form.valid_until} onChange={set("valid_until")} /></Field>
        </div>
        <Field label="Limit to products (none selected = all products)" error={errors.product_ids}>
          <select multiple size={Math.min(6, Math.max(3, products.length))} value={productIds.map(String)} onChange={(e) => setProductIds(Array.from(e.target.selectedOptions, (o) => Number(o.value)))}>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Save</button>
        </div>
      </form>
    </Modal>
  );
}
