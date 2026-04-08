export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export async function fetchWithRetry(url: string, options: RequestInit = {}, retries = 2): Promise<Response> {
  for (let i = 0; i <= retries; i++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      const res = await fetch(`${API_URL}${url}`, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.ok) return res;
    } catch (err) {
      if (i === retries) throw err;
    }
  }
  throw new Error("Failed after retries");
}
