import { Auth0Client } from '@auth0/nextjs-auth0/server';

export function authConfigured() {
  return Boolean(process.env.APP_BASE_URL && process.env.AUTH0_DOMAIN &&
    process.env.AUTH0_CLIENT_ID && process.env.AUTH0_CLIENT_SECRET &&
    process.env.AUTH0_SECRET && process.env.OIDC_AUDIENCE);
}

let client: Auth0Client | undefined;
export function auth0() {
  client ??= new Auth0Client({
    appBaseUrl: process.env.APP_BASE_URL,
    authorizationParameters: { audience: process.env.OIDC_AUDIENCE, scope: 'openid profile' },
    signInReturnToPath: '/dashboard',
    enableAccessTokenEndpoint: false,
  });
  return client;
}
