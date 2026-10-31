import { useCallback, useEffect, useState, type ReactNode } from "react";
import { errorMessage } from "../api/client";
import type { Page } from "../types";

export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps);
  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    run()
      .then(setData)
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, [run]);
  useEffect(reload, [reload]);
  return { data, error, loading, reload, setData };
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="muted">{subtitle}</div>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

export function Loading() {
  return <div className="spinner">Loading…</div>;
}

export function ErrorAlert({ message, onRetry }: { message: string | null; onRetry?: () => void }) {
  if (!message) return null;
  return (
    <div className="alert alert-error" role="alert">
      {message}{" "}
      {onRetry && <button className="link-btn" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function StatusBadge({ status, text }: { status: string; text?: string }) {
  return <span className={`badge ${status}`}>{text ?? status.replace(/_/g, " ")}</span>;
}

export function Pagination<T>({ page, onPage }: { page: Page<T> | null; onPage: (p: number) => void }) {
  if (!page || page.total <= page.page_size) return null;
  const pages = Math.ceil(page.total / page.page_size);
  return (
    <div className="pagination">
      <span className="muted">Page {page.page} of {pages} · {page.total} records</span>
      <button className="btn btn-sm" disabled={page.page <= 1} onClick={() => onPage(page.page - 1)}>Previous</button>
      <button className="btn btn-sm" disabled={page.page >= pages} onClick={() => onPage(page.page + 1)}>Next</button>
    </div>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title, message, confirmLabel = "Confirm", danger, onConfirm, onClose, children,
}: {
  title: string; message: ReactNode; confirmLabel?: string; danger?: boolean;
  onConfirm: () => Promise<void>; onClose: () => void; children?: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={title} onClose={busy ? () => undefined : onClose}>
      <ErrorAlert message={error} />
      <div>{message}</div>
      {children}
      <div className="modal-actions">
        <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
        <button className={danger ? "btn btn-danger" : "btn btn-primary"} onClick={confirm} disabled={busy}>
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="field">
      {label}
      {children}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}
