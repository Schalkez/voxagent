/**
 * VoxAgent API Client
 *
 * Base HTTP client for communicating with the Python FastAPI management server.
 */

const API_BASE =
  import.meta.env.VITE_API_URL || 'http://localhost:8642';

export async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const resp = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!resp.ok) {
    const error = await resp.text();
    throw new Error(`API ${resp.status}: ${error}`);
  }

  return resp.json() as Promise<T>;
}
