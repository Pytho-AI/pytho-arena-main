export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = init.body instanceof FormData
    ? init.headers
    : { "Content-Type": "application/json", ...init.headers };
  const response = await fetch(path, {
    ...init,
    headers,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc?.join(".")}: ${item.msg}`).join("; ")
      : detail || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body as T;
}
