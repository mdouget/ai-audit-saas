# AI Assurance — MVP implementation plan

## Scope
A standalone multi-tenant SaaS for organizational AI risk assessments. Features: client and assessment management; AI risk/readiness questionnaire; NIST AI RMF-aligned control library; weighted scoring; findings dashboard; AI-assisted remediation; executive PDF; 30/60/90-day plan; assessment history and reassessment.

## Architecture
Next.js/TypeScript frontend, FastAPI/Python backend, PostgreSQL database with migrations, private Azure blob storage, OIDC login, asynchronous worker and external AI processing only with customer authorization. Deploy to Azure Container Apps with managed PostgreSQL, Key Vault and monitoring.

## Tables
organizations, users, memberships, invitations, framework_versions, controls, questions, question_control_mappings, assessments, assessment_responses, evidence, assessment_scores, findings, remediation_tasks, assessment_snapshots, reports, jobs, audit_events. Tenant-owned data must carry organization_id and enforce both application authorization and PostgreSQL row-level security.

## Screens
Organization setup, executive dashboard, assessments, questionnaire, controls, findings, remediation planner, report center, assessment history, account/security settings.

## Planned API
POST /api/v1/organizations; POST/GET /api/v1/assessments; PUT /api/v1/assessments/{id}/responses/{questionId}; POST /api/v1/assessments/{id}/submit; POST /api/v1/assessments/{id}/finalize; GET /api/v1/assessments/{id}/scores; GET /api/v1/assessments/{id}/findings; POST /api/v1/findings/{id}/recommendations; POST /api/v1/assessments/{id}/roadmap; POST /api/v1/assessments/{id}/reports; POST /api/v1/assessments/{id}/reassess.

## Scoring
Custom 0/25/50/75/100 maturity statuses, excluding justified N/A. Unknown lowers coverage; a domain must have at least 80% answered coverage. Domain weights: governance 30%, security 30%, privacy 20%, vendor oversight 10%, operational readiness 10%. Separate risk matrix: likelihood 1–5 x impact 1–5. Scores are not NIST-issued certification.

## Security criteria
Managed OIDC with MFA, strict tenant isolation, resource-level access, RLS as defense in depth, safe evidence ingestion, controlled AI data sharing, secret management, append-only audit events, rate limits, backup and restore tests, cross-tenant tests, human-approved AI recommendations. No real customer data until these gates are in place.

## Roadmap
PR1: foundation, tenancy, authorization. PR2: control library and questionnaire. PR3: scoring/findings/dashboard. PR4: AI recommendations/roadmap/PDF. PR5: reassessment/security hardening/beta.

## Tenant workspace milestone

The first functional milestone adds PostgreSQL migrations, Auth0 OIDC login, local user provisioning, organizations and memberships, and draft assessment management. The dashboard supports onboarding, switching organizations, and creating, editing, archiving and restoring drafts. Membership management uses registered account IDs. The API resolves membership for each requested organization before issuing scoped queries, and the runtime role is subject to forced PostgreSQL row-level security.

The control library, questionnaire, evidence, assessment scoring integration, audit trail, remediation, reports, and billing remain roadmap work. The demo scoring endpoint remains separate from authenticated assessments.
