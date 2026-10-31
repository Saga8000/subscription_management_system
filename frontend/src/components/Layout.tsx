import { useState } from "react";
import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { isInternal, useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { Role } from "../types";
import { Loading } from "./ui";

const NAV: { to: string; label: string; roles: Role[] }[] = [
  { to: "/dashboard", label: "Dashboard", roles: ["admin", "staff"] },
  { to: "/portal", label: "My account", roles: ["customer"] },
  { to: "/customers", label: "Customers", roles: ["admin", "staff"] },
  { to: "/products", label: "Products", roles: ["admin", "staff"] },
  { to: "/plans", label: "Plans", roles: ["admin", "staff"] },
  { to: "/quotation-templates", label: "Quotation templates", roles: ["admin", "staff"] },
  { to: "/quotations", label: "Quotations", roles: ["admin", "staff", "customer"] },
  { to: "/subscriptions", label: "Subscriptions", roles: ["admin", "staff", "customer"] },
  { to: "/invoices", label: "Invoices", roles: ["admin", "staff", "customer"] },
  { to: "/payments", label: "Payments", roles: ["admin", "staff", "customer"] },
  { to: "/discounts", label: "Discounts", roles: ["admin", "staff"] },
  { to: "/taxes", label: "Taxes", roles: ["admin", "staff"] },
  { to: "/users", label: "Users", roles: ["admin"] },
];

export function Layout() {
  const { user, loading, logout } = useAuth();
  const toast = useToast();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  return (
    <div className="layout">
      <nav className={`sidebar${open ? " open" : ""}`} onClick={() => setOpen(false)}>
        <div className="brand">Brightloop</div>
        {NAV.filter((n) => n.roles.includes(user.role)).map((n) => (
          <NavLink key={n.to} to={n.to}>{n.label}</NavLink>
        ))}
      </nav>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-sm menu-toggle" onClick={() => setOpen(!open)} aria-label="Toggle menu">Menu</button>
          <span className="muted">{isInternal(user) ? "Back office" : "Customer portal"}</span>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span>{user.full_name} <span className="badge">{user.role}</span></span>
            <button
              className="btn btn-sm"
              onClick={() => logout().then(() => toast.success("Signed out."))}
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function RequireRole({ roles, children }: { roles: Role[]; children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={isInternal(user) ? "/dashboard" : "/portal"} replace />;
  return children;
}
