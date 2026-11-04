import 'server-only';
import { redirect } from 'next/navigation';
import { auth0 } from './auth0';

export async function api(path: string, method = 'GET', body?: object) {
  const client = auth0();
  if (!(await client.getSession())) redirect('/auth/login');
  const access = await client.getAccessToken().catch(() => null);
  if (!access) redirect('/auth/login');
  const base = process.env.INTERNAL_API_URL ?? 'http://127.0.0.1:8000';
  return fetch(base + '/api/v1' + path, {
    method,
    cache: 'no-store',
    redirect: 'error',
    signal: AbortSignal.timeout(10000),
    headers: { Authorization: 'Bearer ' + access.token, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
