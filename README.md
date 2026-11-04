# AI Assurance

AI governance, security, risk and readiness assessment. This milestone adds a local, tenant-scoped workspace for organization onboarding, membership management, and assessment drafts.

## Local setup

1. Copy `.env.example` to `.env`. Use a development Auth0 tenant and synthetic accounts.
2. Create an Auth0 Regular Web Application and an Auth0 custom API. Configure the API with RS256 signing and the Auth0 access token profile. Set the API identifier as `OIDC_AUDIENCE`, distinct from the client ID. Enable MFA in the Auth0 tenant. Configure the application to use interactive login and disable unused grants such as client credentials.
3. Set the callback URL to `http://localhost:3000/auth/callback` and the allowed logout URL to `http://localhost:3000`. Set `AUTH0_DOMAIN` to the Auth0 hostname and `OIDC_ISSUER_URL` to the matching HTTPS issuer, including its trailing slash. Set the client ID and client secret from the Auth0 application. Generate `AUTH0_SECRET` with `openssl rand -hex 32` or an equivalent cryptographic random generator.
4. Run `docker compose up --build`. Open [the local workspace](http://localhost:3000/dashboard). The one-shot migration service applies migrations before the API starts. The bundled database role initialization runs on a fresh volume.
5. Sign in and create an organization. An owner can add a registered user by the account ID shown on that user's dashboard. Members can create, edit, archive and restore assessments. Organization settings and roster changes require the owner.

The API is available locally at [Swagger UI](http://localhost:8000/docs). Use an Auth0 access token issued to the configured web client for the configured API audience. Assessment routes take the selected organization UUID in the `organization_id` query parameter. The dashboard keeps access tokens on the server and uses the Auth0 SDK's session and login flow.

## Database roles and tests

The Compose credentials are local fixtures. For a separate database, provision the dedicated `assurance_app` login with its own secret and no role memberships, administrative privileges, or table ownership. Give a separate migration login schema creation rights and ownership of the migration objects. Run `python -m app.migrate` from `apps/api` with `MIGRATION_DATABASE_URL`. Supply only the restricted `DATABASE_URL` to the runtime. The application scopes each request in its own transaction and checks membership before setting tenant context. PostgreSQL applies row policies to the runtime role as defense against queries that omit tenant predicates.

Install `apps/api/requirements.txt` and run `python -m pytest -q` from `apps/api` with `PYTHONPATH=.`. To run the integration suite, supply `TEST_MIGRATION_DATABASE_URL` and `TEST_DATABASE_URL` for an isolated PostgreSQL database, with the runtime login provisioned first. CI uses PostgreSQL 16. Run `npm ci`, `npm run lint` and `npm run build` from `apps/web` for frontend checks.

Use synthetic data in this milestone. See [the implementation plan](docs/IMPLEMENTATION.md) for the remaining scope and security gates.
