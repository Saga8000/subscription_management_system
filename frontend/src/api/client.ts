export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function qs(params: Query): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      credentials: "same-origin",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Check that the backend is running.");
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const err = data?.error ?? {};
    if (response.status === 401) window.dispatchEvent(new Event("auth:unauthorized"));
    throw new ApiError(response.status, err.code ?? "error", err.message ?? `Request failed (${response.status})`, err.fields ?? {});
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, query: Query = {}) => request<T>("GET", path + qs(query)),
  post: <T>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
};

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

export function fieldErrors(err: unknown): Record<string, string> {
  return err instanceof ApiError ? err.fields : {};
}
