const currency = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });
const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return currency.format(Number(value));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return dateFmt.format(new Date(y, m - 1, d));
}

export function label(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function cadence(period: string, interval: number): string {
  const unit = { daily: "day", weekly: "week", monthly: "month", yearly: "year" }[period] ?? period;
  return interval === 1 ? `Every ${unit}` : `Every ${interval} ${unit}s`;
}

export function quotationStatusLabel(status: string): string {
  return status === "sent" ? "Quotation sent" : label(status);
}
