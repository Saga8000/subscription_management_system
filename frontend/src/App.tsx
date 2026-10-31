import { Navigate, Route, Routes } from "react-router-dom";
import { Layout, RequireRole } from "./components/Layout";
import { isInternal, useAuth } from "./context/AuthContext";
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from "./pages/AuthPages";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DiscountsPage } from "./pages/DiscountsPage";
import { InvoiceDetailPage, InvoicesPage } from "./pages/InvoicesPages";
import { PaymentsPage } from "./pages/PaymentsPage";
import { PlansPage } from "./pages/PlansPage";
import { PortalPage } from "./pages/PortalPage";
import { ProductsPage } from "./pages/ProductsPage";
import { QuotationDetailPage, QuotationFormPage, QuotationsPage } from "./pages/QuotationsPages";
import { SubscriptionDetailPage, SubscriptionsPage } from "./pages/SubscriptionsPages";
import { TaxesPage } from "./pages/TaxesPage";
import { TemplatesPage } from "./pages/TemplatesPage";
import { UsersPage } from "./pages/UsersPage";
import { Loading } from "./components/ui";

const STAFF = ["admin", "staff"] as const;

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={isInternal(user) ? "/dashboard" : "/portal"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<RequireRole roles={[...STAFF]}><DashboardPage /></RequireRole>} />
        <Route path="/portal" element={<RequireRole roles={["customer"]}><PortalPage /></RequireRole>} />
        <Route path="/customers" element={<RequireRole roles={[...STAFF]}><CustomersPage /></RequireRole>} />
        <Route path="/products" element={<RequireRole roles={[...STAFF]}><ProductsPage /></RequireRole>} />
        <Route path="/plans" element={<RequireRole roles={[...STAFF]}><PlansPage /></RequireRole>} />
        <Route path="/quotation-templates" element={<RequireRole roles={[...STAFF]}><TemplatesPage /></RequireRole>} />
        <Route path="/quotations" element={<QuotationsPage />} />
        <Route path="/quotations/new" element={<RequireRole roles={[...STAFF]}><QuotationFormPage /></RequireRole>} />
        <Route path="/quotations/:id/edit" element={<RequireRole roles={[...STAFF]}><QuotationFormPage /></RequireRole>} />
        <Route path="/quotations/:id" element={<QuotationDetailPage />} />
        <Route path="/subscriptions" element={<SubscriptionsPage />} />
        <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
        <Route path="/invoices" element={<InvoicesPage />} />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="/payments" element={<PaymentsPage />} />
        <Route path="/discounts" element={<RequireRole roles={[...STAFF]}><DiscountsPage /></RequireRole>} />
        <Route path="/taxes" element={<RequireRole roles={[...STAFF]}><TaxesPage /></RequireRole>} />
        <Route path="/users" element={<RequireRole roles={["admin"]}><UsersPage /></RequireRole>} />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
