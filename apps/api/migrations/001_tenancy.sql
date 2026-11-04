CREATE SCHEMA assurance;
SET LOCAL search_path = assurance, pg_catalog;

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer text NOT NULL,
    subject text NOT NULL,
    UNIQUE (issuer, subject)
);

CREATE TABLE organizations (
    id uuid PRIMARY KEY,
    name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
    organization_id uuid NOT NULL REFERENCES organizations(id),
    user_id uuid NOT NULL REFERENCES users(id),
    role text NOT NULL CHECK (role IN ('owner', 'member')),
    PRIMARY KEY (organization_id, user_id)
);
CREATE INDEX memberships_user_idx ON memberships (user_id, organization_id);
CREATE UNIQUE INDEX memberships_one_owner ON memberships (organization_id) WHERE role = 'owner';

CREATE TABLE assessments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id),
    title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 160),
    description text NOT NULL DEFAULT '' CHECK (char_length(description) <= 4000),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'archived')),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
CREATE INDEX assessments_org_created_idx ON assessments (organization_id, created_at DESC, id DESC);

CREATE FUNCTION actor_issuer() RETURNS text LANGUAGE sql STABLE
    RETURN nullif(current_setting('assurance.issuer', true), '');
CREATE FUNCTION actor_subject() RETURNS text LANGUAGE sql STABLE
    RETURN nullif(current_setting('assurance.subject', true), '');
CREATE FUNCTION actor_id() RETURNS uuid LANGUAGE sql STABLE
    RETURN (SELECT id FROM assurance.users WHERE issuer = assurance.actor_issuer() AND subject = assurance.actor_subject());
CREATE FUNCTION tenant_id() RETURNS uuid LANGUAGE sql STABLE
    RETURN nullif(current_setting('assurance.organization_id', true), '')::uuid;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessments FORCE ROW LEVEL SECURITY;

CREATE POLICY own_identity ON users
    USING (issuer = assurance.actor_issuer() AND subject = assurance.actor_subject())
    WITH CHECK (issuer = assurance.actor_issuer() AND subject = assurance.actor_subject());

-- The helper checks ownership without recursively applying the membership policy.
-- Its owner policy is scoped to the verified actor, even with FORCE RLS enabled.
CREATE POLICY organization_owner_lookup ON organizations FOR SELECT TO CURRENT_USER
    USING (created_by = assurance.actor_id());
CREATE FUNCTION owns_organization(target uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
    RETURN EXISTS (
        SELECT FROM assurance.organizations
        WHERE id = target AND created_by = assurance.actor_id()
    );
REVOKE ALL ON FUNCTION owns_organization(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION owns_organization(uuid) TO assurance_app;

CREATE POLICY membership_read ON memberships FOR SELECT
    USING (
        (user_id = assurance.actor_id()
         AND (assurance.tenant_id() IS NULL OR organization_id = assurance.tenant_id()))
        OR (organization_id = assurance.tenant_id() AND assurance.owns_organization(organization_id))
    );
CREATE POLICY organization_read ON organizations FOR SELECT TO assurance_app
    USING (
        (assurance.tenant_id() IS NULL OR id = assurance.tenant_id())
        AND EXISTS (
            SELECT FROM assurance.memberships m
            WHERE m.organization_id = organizations.id AND m.user_id = assurance.actor_id()
        )
    );
CREATE POLICY organization_create ON organizations FOR INSERT
    WITH CHECK (id = assurance.tenant_id() AND created_by = assurance.actor_id());
CREATE POLICY organization_update ON organizations FOR UPDATE
    USING (id = assurance.tenant_id() AND created_by = assurance.actor_id());

CREATE POLICY membership_create ON memberships FOR INSERT
    WITH CHECK (
        organization_id = assurance.tenant_id()
        AND assurance.owns_organization(organization_id)
        AND ((role = 'owner' AND user_id = assurance.actor_id())
             OR (role = 'member' AND user_id <> assurance.actor_id()))
    );
CREATE POLICY membership_remove ON memberships FOR DELETE
    USING (
        role = 'member' AND organization_id = assurance.tenant_id()
        AND assurance.owns_organization(organization_id)
    );

CREATE POLICY assessment_tenant ON assessments
    USING (
        organization_id = assurance.tenant_id()
        AND EXISTS (
            SELECT FROM assurance.memberships m
            WHERE m.organization_id = assessments.organization_id
              AND m.user_id = assurance.actor_id()
        )
    );
CREATE POLICY assessment_author ON assessments AS RESTRICTIVE FOR INSERT
    WITH CHECK (created_by = assurance.actor_id());

GRANT USAGE ON SCHEMA assurance TO assurance_app;
GRANT SELECT ON users, organizations, memberships, assessments TO assurance_app;
GRANT INSERT (issuer, subject) ON users TO assurance_app;
GRANT INSERT (id, name, created_by) ON organizations TO assurance_app;
GRANT INSERT ON memberships TO assurance_app;
GRANT DELETE ON memberships TO assurance_app;
GRANT UPDATE (name) ON organizations TO assurance_app;
GRANT INSERT (organization_id, title, description, created_by) ON assessments TO assurance_app;
GRANT UPDATE (title, description, status, updated_at) ON assessments TO assurance_app;
