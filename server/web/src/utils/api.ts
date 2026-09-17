export const API_BASE = window.location.origin;

export async function api<T = any>(path: string, opts: RequestInit & { json?: any } = {}): Promise<T> {
  const headers = new Headers(opts.headers || {});
  
  const token = localStorage.getItem('access_token');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (opts.json) {
    headers.set('Content-Type', 'application/json');
    opts.body = JSON.stringify(opts.json);
  }

  // Remove custom json field as fetch doesn't accept it
  const { json, ...fetchOpts } = opts;

  const res = await fetch(API_BASE + path, { ...fetchOpts, headers });
  const ct = res.headers.get('content-type') || '';
  
  const data = ct.includes('application/json') ? await res.json() : await res.text();
  
  if (!res.ok) {
    let errorMessage = res.statusText;
    if (data && data.detail) {
      errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    } else if (typeof data === 'string' && data) {
      errorMessage = data;
    }
    
    // Auth expired or invalid, handled centrally
    if (res.status === 401) {
      localStorage.removeItem('access_token');
      window.dispatchEvent(new CustomEvent('auth:401'));
    }

    throw new Error(errorMessage);
  }
  
  return data;
}
