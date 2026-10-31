import { useState, type FormEvent } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { Empty, ErrorAlert, Field, Loading, Modal, PageHeader, Pagination, StatusBadge, useAsync } from "../components/ui";
import { useToast } from "../context/ToastContext";
import type { Page, Product, Tax, Variant } from "../types";
import { label, money } from "../utils/format";

export function ProductsPage() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useAsync(() => api.get<Page<Product>>("/products", { q, page }), [q, page]);
  const taxes = useAsync(() => api.get<Tax[]>("/taxes"), []);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [variantsFor, setVariantsFor] = useState<Product | null>(null);

  return (
    <>
      <PageHeader title="Products" actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>New product</button>} />
      <div className="filters"><input placeholder="Search products" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && data.items.length === 0 ? <Empty>No products yet.</Empty> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Type</th><th className="num">Sales price</th><th className="num">Cost</th><th>Tax</th><th>Variants</th><th>Status</th><th /></tr></thead>
            <tbody>{data.items.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td><td>{label(p.product_type)}</td>
                <td className="num">{money(p.sales_price)}</td><td className="num">{money(p.cost_price)}</td>
                <td>{p.tax ? `${p.tax.name} (${Number(p.tax.rate_percent)}%)` : "—"}</td>
                <td>{p.variants.length ? p.variants.map((v) => `${v.name} ${money(v.unit_price)}`).join(", ") : "—"}</td>
                <td><StatusBadge status={p.is_active ? "active" : "closed"} text={p.is_active ? "active" : "archived"} /></td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-sm" onClick={() => setEditing(p)}>Edit</button>
                  <button className="btn btn-sm" onClick={() => setVariantsFor(p)}>Variants</button>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <Pagination page={data} onPage={setPage} />
      </div>
      {editing && <ProductForm product={editing === "new" ? null : editing} taxes={taxes.data ?? []} onClose={() => setEditing(null)} onSaved={reload} />}
      {variantsFor && <VariantsEditor product={variantsFor} onClose={() => setVariantsFor(null)} onSaved={(p) => { setVariantsFor(p); reload(); }} />}
    </>
  );
}

function ProductForm({ product, taxes, onClose, onSaved }: { product: Product | null; taxes: Tax[]; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    name: product?.name ?? "", product_type: product?.product_type ?? "service",
    sales_price: product?.sales_price ?? "", cost_price: product?.cost_price ?? "0",
    tax_id: product?.tax_id ? String(product.tax_id) : "", notes: product?.notes ?? "", is_active: product?.is_active ?? true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = {
      name: form.name, product_type: form.product_type, sales_price: form.sales_price, cost_price: form.cost_price || "0",
      tax_id: form.tax_id ? Number(form.tax_id) : null, notes: form.notes || null, is_active: form.is_active,
    };
    try {
      if (product) await api.patch(`/products/${product.id}`, body);
      else await api.post("/products", body);
      toast.success(product ? "Product updated." : "Product created.");
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
    <Modal title={product ? "Edit product" : "New product"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="form-row">
          <Field label="Name" error={errors.name}><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Type" error={errors.product_type}>
            <select value={form.product_type} onChange={(e) => setForm({ ...form, product_type: e.target.value as Product["product_type"] })}>
              <option value="service">Service</option><option value="goods">Goods</option>
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field label="Sales price (₹)" error={errors.sales_price}><input type="number" min="0" step="0.01" required value={form.sales_price} onChange={(e) => setForm({ ...form, sales_price: e.target.value })} /></Field>
          <Field label="Cost price (₹)" error={errors.cost_price}><input type="number" min="0" step="0.01" value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} /></Field>
          <Field label="Default tax" error={errors.tax_id}>
            <select value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })}>
              <option value="">No tax</option>
              {taxes.filter((t) => t.is_active || String(t.id) === form.tax_id).map((t) => <option key={t.id} value={t.id}>{t.name} ({Number(t.rate_percent)}%)</option>)}
            </select>
          </Field>
        </div>
        <Field label="Notes" error={errors.notes}><textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
        <label className="check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active (available for new quotations)</label>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Modal>
  );
}

function VariantsEditor({ product, onClose, onSaved }: { product: Product; onClose: () => void; onSaved: (p: Product) => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ name: "", extra_price: "0" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await api.post<Product>(`/products/${product.id}/variants`, form);
      toast.success("Variant added.");
      setForm({ name: "", extra_price: "0" });
      onSaved(updated);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const toggle = async (v: Variant) => {
    try {
      onSaved(await api.patch<Product>(`/products/${product.id}/variants/${v.id}`, { is_active: !v.is_active }));
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <Modal title={`Variants – ${product.name}`} onClose={onClose}>
      <ErrorAlert message={error} />
      <div className="muted" style={{ marginBottom: 8 }}>Base price {money(product.sales_price)}. Variant price = base price + extra price.</div>
      {product.variants.length === 0 ? <Empty>No variants yet.</Empty> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Name</th><th className="num">Extra</th><th className="num">Unit price</th><th>Status</th><th /></tr></thead>
          <tbody>{product.variants.map((v) => (
            <tr key={v.id}><td>{v.name}</td><td className="num">{money(v.extra_price)}</td><td className="num">{money(v.unit_price)}</td>
              <td><StatusBadge status={v.is_active ? "active" : "closed"} text={v.is_active ? "active" : "inactive"} /></td>
              <td><button className="btn btn-sm" onClick={() => toggle(v)}>{v.is_active ? "Deactivate" : "Activate"}</button></td></tr>
          ))}</tbody>
        </table></div>
      )}
      <form className="form-row" onSubmit={add} style={{ marginTop: 12, alignItems: "end" }}>
        <Field label="Variant name"><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Extra price (₹)"><input type="number" step="0.01" required value={form.extra_price} onChange={(e) => setForm({ ...form, extra_price: e.target.value })} /></Field>
        <button className="btn btn-primary" disabled={busy}>Add variant</button>
      </form>
      <div className="modal-actions"><button className="btn" onClick={onClose}>Close</button></div>
    </Modal>
  );
}
