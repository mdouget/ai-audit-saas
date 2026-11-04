from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from psycopg import errors
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from .auth import Identity, authenticate
from .db import Database, provision_user, set_tenant

router = APIRouter(prefix="/api/v1")
Authenticated = Annotated[Identity, Depends(authenticate)]
OrganizationName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^\x00]*$")]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=r"^[^\x00]*$")]
Description = Annotated[str, StringConstraints(max_length=4000, pattern=r"^[^\x00]*$")]
ASSESSMENT_FIELDS = "id, organization_id, title, description, status, created_by, created_at, updated_at"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationInput(Input):
    name: OrganizationName


class MemberInput(Input):
    user_id: UUID


class AssessmentInput(Input):
    title: Title
    description: Description = ""


class AssessmentUpdate(Input):
    title: Title | None = None
    description: Description | None = None
    status: Literal["draft", "archived"] | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set or any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Provide at least one field and omit unchanged fields")
        return self


def authorize(conn, organization_id: UUID, *, owner: bool = False):
    membership = conn.execute("""
        SELECT role FROM assurance.memberships
        WHERE organization_id = %s AND user_id = assurance.actor_id()
    """, (organization_id,)).fetchone()
    if not membership:
        raise HTTPException(404, "Organization not found")
    if owner and membership["role"] != "owner":
        raise HTTPException(403, "Organization owner required")
    set_tenant(conn, organization_id)
    return membership["role"]


@router.get("/me")
def me(conn: Database, identity: Authenticated):
    return {"id": provision_user(conn, identity)}


@router.get("/organizations")
def organizations(conn: Database):
    return conn.execute("""
        SELECT o.id, o.name, m.role
        FROM assurance.organizations o
        JOIN assurance.memberships m ON m.organization_id = o.id
        WHERE m.user_id = assurance.actor_id()
        ORDER BY o.created_at, o.id
    """).fetchall()


@router.post("/organizations", status_code=201)
def create_organization(body: OrganizationInput, conn: Database, identity: Authenticated):
    user_id = provision_user(conn, identity)
    organization_id = uuid4()
    set_tenant(conn, organization_id)
    conn.execute(
        "INSERT INTO assurance.organizations (id, name, created_by) VALUES (%s, %s, %s)",
        (organization_id, body.name, user_id),
    )
    conn.execute("""
        INSERT INTO assurance.memberships (organization_id, user_id, role)
        VALUES (%s, %s, 'owner')
    """, (organization_id, user_id))
    return {"id": organization_id, "name": body.name, "role": "owner"}


@router.patch("/organizations/{organization_id}")
def rename_organization(organization_id: UUID, body: OrganizationInput, conn: Database):
    authorize(conn, organization_id, owner=True)
    conn.execute("UPDATE assurance.organizations SET name = %s WHERE id = %s", (body.name, organization_id))
    return {"id": organization_id, "name": body.name, "role": "owner"}


@router.get("/organizations/{organization_id}/members")
def members(organization_id: UUID, conn: Database):
    authorize(conn, organization_id, owner=True)
    return conn.execute("""
        SELECT user_id, role FROM assurance.memberships
        WHERE organization_id = %s ORDER BY role DESC, user_id
    """, (organization_id,)).fetchall()


@router.post("/organizations/{organization_id}/members", status_code=201)
def add_member(organization_id: UUID, body: MemberInput, conn: Database):
    authorize(conn, organization_id, owner=True)
    try:
        member = conn.execute("""
            INSERT INTO assurance.memberships (organization_id, user_id, role)
            SELECT %s, %s, 'member' WHERE %s <> assurance.actor_id()
            ON CONFLICT DO NOTHING RETURNING user_id, role
        """, (organization_id, body.user_id, body.user_id)).fetchone()
    except errors.ForeignKeyViolation:
        raise HTTPException(404, "User not found") from None
    if not member:
        raise HTTPException(409, "User is already a member")
    return member


@router.delete("/organizations/{organization_id}/members/{user_id}", status_code=204)
def remove_member(organization_id: UUID, user_id: UUID, conn: Database):
    authorize(conn, organization_id, owner=True)
    deleted = conn.execute("""
        DELETE FROM assurance.memberships WHERE organization_id = %s AND user_id = %s AND role = 'member'
    """, (organization_id, user_id))
    if not deleted.rowcount:
        raise HTTPException(404, "Removable member not found")
    return Response(status_code=204)


def scoped_organization(organization_id: UUID, conn: Database) -> UUID:
    authorize(conn, organization_id)
    return organization_id


Tenant = Annotated[UUID, Depends(scoped_organization)]


@router.get("/assessments")
def assessments(conn: Database, organization_id: Tenant, limit: Annotated[int, Query(ge=1, le=100)] = 50,
                offset: Annotated[int, Query(ge=0, le=2147483647)] = 0):
    return conn.execute(f"""
        SELECT {ASSESSMENT_FIELDS} FROM assurance.assessments
        WHERE organization_id = %s ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s
    """, (organization_id, limit, offset)).fetchall()


@router.post("/assessments", status_code=201)
def create_assessment(body: AssessmentInput, conn: Database, organization_id: Tenant):
    return conn.execute(f"""
        INSERT INTO assurance.assessments (organization_id, title, description, created_by)
        VALUES (%s, %s, %s, assurance.actor_id()) RETURNING {ASSESSMENT_FIELDS}
    """, (organization_id, body.title, body.description)).fetchone()


@router.get("/assessments/{assessment_id}")
def assessment(assessment_id: UUID, conn: Database, organization_id: Tenant):
    item = conn.execute(f"""
        SELECT {ASSESSMENT_FIELDS} FROM assurance.assessments WHERE organization_id = %s AND id = %s
    """, (organization_id, assessment_id)).fetchone()
    if not item:
        raise HTTPException(404, "Assessment not found")
    return item


@router.patch("/assessments/{assessment_id}")
def update_assessment(assessment_id: UUID, body: AssessmentUpdate, conn: Database, organization_id: Tenant):
    item = conn.execute(f"""
        UPDATE assurance.assessments
        SET title = coalesce(%s, title), description = coalesce(%s, description),
            status = coalesce(%s, status), updated_at = now()
        WHERE organization_id = %s AND id = %s RETURNING {ASSESSMENT_FIELDS}
    """, (body.title, body.description, body.status, organization_id, assessment_id)).fetchone()
    if not item:
        raise HTTPException(404, "Assessment not found")
    return item
