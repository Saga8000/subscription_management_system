import { useState, type FormEvent } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { passwordProblems } from "./AuthPages";
import { ConfirmDialog, ErrorAlert, Field, Loading, Modal, PageHeader, StatusBadge, useAsync } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { User } from "../types";

export function UsersPage() {
  const { user: me } = useAuth();
  const toast = useToast();
  const { data, error, loading, reload } = useAsync(() => api.get<User[]>("/users"), []);
  const [creating, setCreating] = useState(false);
  const [toggling, setToggling] = useState<User | null>(null);
  return (
    <>
      <PageHeader title="Users" actions={<button className="btn btn-primary" onClick={() => setCreating(true)}>New staff user</button>} />
      <ErrorAlert message={error} onRetry={reload} />
      <div className="card">
        {loading && !data ? <Loading /> : data && (
          <div className="table-wrap"><table>
            <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
            <tbody>{data.map((u) => (
              <tr key={u.id}><td>{u.full_name}</td><td>{u.email}</td><td><span className="badge">{u.role}</span></td>
                <td><StatusBadge status={u.is_active ? "active" : "closed"} text={u.is_active ? "active" : "disabled"} /></td>
                <td>{u.id !== me?.id && <button className="btn btn-sm" onClick={() => setToggling(u)}>{u.is_active ? "Disable" : "Enable"}</button>}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {creating && <StaffForm onClose={() => setCreating(false)} onSaved={reload} />}
      {toggling && (
        <ConfirmDialog
          title={toggling.is_active ? "Disable user?" : "Enable user?"}
          message={toggling.is_active ? `${toggling.email} will be signed out and unable to sign in.` : `${toggling.email} will be able to sign in again.`}
          danger={toggling.is_active}
          onConfirm={async () => {
            await api.patch(`/users/${toggling.id}`, { is_active: !toggling.is_active });
            toast.success("User updated.");
            reload();
          }}
          onClose={() => setToggling(null)}
        />
      )}
    </>
  );
}

function StaffForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "staff" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblems(form.password);
    if (problems.length) return setErrors({ password: `Password needs ${problems.join(", ")}.` });
    setBusy(true);
    setError(null);
    try {
      await api.post("/users", form);
      toast.success("User created.");
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
    <Modal title="New staff user" onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <ErrorAlert message={error} />
        <Field label="Full name" error={errors.full_name}><input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
        <Field label="Email" error={errors.email}><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Initial password" error={errors.password}><input type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        <Field label="Role" error={errors.role}>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="staff">Staff</option><option value="admin">Admin</option></select>
        </Field>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Create</button>
        </div>
      </form>
    </Modal>
  );
}
