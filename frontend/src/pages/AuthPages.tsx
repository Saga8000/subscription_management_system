import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, errorMessage, fieldErrors } from "../api/client";
import { ErrorAlert, Field } from "../components/ui";
import { isInternal, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function passwordProblems(password: string): string[] {
  const problems: string[] = [];
  if (password.length <= 8) problems.push("more than 8 characters");
  if (!/[a-z]/.test(password)) problems.push("a lowercase letter");
  if (!/[A-Z]/.test(password)) problems.push("an uppercase letter");
  if (!/[^A-Za-z0-9]/.test(password)) problems.push("a special character");
  return problems;
}

function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="muted" style={{ marginBottom: 4 }}>Brightloop Subscriptions</div>
        <h1 style={{ marginBottom: 16 }}>{title}</h1>
        {children}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={isInternal(user) ? "/dashboard" : "/portal"} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? (isInternal(u) ? "/dashboard" : "/portal"), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Sign in">
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        <Field label="Email"><input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Link to="/register">Create an account</Link>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
      </form>
    </AuthCard>
  );
}

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    const problems = passwordProblems(form.password);
    if (problems.length) local.password = `Password needs ${problems.join(", ")}.`;
    if (form.password !== form.confirm) local.confirm = "Passwords do not match.";
    setErrors(local);
    if (Object.keys(local).length) return;
    setBusy(true);
    setError(null);
    try {
      await register(form.full_name, form.email, form.password);
      toast.success("Account created. Welcome!");
      navigate("/portal", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setErrors(fieldErrors(err));
    } finally {
      setBusy(false);
    }
  };
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value });

  return (
    <AuthCard title="Create your account">
      <form className="form" onSubmit={submit} noValidate>
        <ErrorAlert message={error} />
        <Field label="Full name" error={errors.full_name}><input required maxLength={120} value={form.full_name} onChange={set("full_name")} /></Field>
        <Field label="Email" error={errors.email}><input type="email" required value={form.email} onChange={set("email")} /></Field>
        <Field label="Password" error={errors.password}><input type="password" autoComplete="new-password" value={form.password} onChange={set("password")} /></Field>
        <div className="muted">More than 8 characters, with uppercase, lowercase and a special character.</div>
        <Field label="Confirm password" error={errors.confirm}><input type="password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} /></Field>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        <Link to="/login">Already have an account? Sign in</Link>
      </form>
    </AuthCard>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<{ message: string; dev_reset_token: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.post("/auth/forgot-password", { email }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Reset your password">
      <form className="form" onSubmit={submit}>
        <ErrorAlert message={error} />
        {result && (
          <div className="alert alert-info">
            {result.message}
            {result.dev_reset_token && (
              <div style={{ marginTop: 8 }}>
                Development mode (no email service):{" "}
                <Link to={`/reset-password?token=${encodeURIComponent(result.dev_reset_token)}`}>open the reset link</Link>
              </div>
            )}
          </div>
        )}
        <Field label="Email"><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Sending…" : "Send reset link"}</button>
        <Link to="/login">Back to sign in</Link>
      </form>
    </AuthCard>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string>();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const token = params.get("token") ?? "";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problems = passwordProblems(password);
    setFieldError(problems.length ? `Password needs ${problems.join(", ")}.` : undefined);
    if (problems.length) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      toast.success("Password updated. Please sign in.");
      navigate("/login", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Choose a new password">
      {!token ? (
        <div className="alert alert-error">This reset link is missing its token. <Link to="/forgot-password">Request a new one</Link>.</div>
      ) : (
        <form className="form" onSubmit={submit} noValidate>
          <ErrorAlert message={error} />
          <Field label="New password" error={fieldError}><input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Update password"}</button>
        </form>
      )}
    </AuthCard>
  );
}
