from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt
import psycopg
import pytest

from app import auth
from app.auth import Identity
from app.db import set_actor, set_tenant
from app.main import app
from app.migrate import migrate

ISSUER = "https://synthetic.example/"
AUDIENCE = "https://synthetic.example/assurance"
CLIENT_ID = "synthetic-web"


@pytest.fixture(scope="module")
def database():
    dsn = os.getenv("TEST_DATABASE_URL")
    migration_dsn = os.getenv("TEST_MIGRATION_DATABASE_URL")
    if not dsn and not migration_dsn:
        pytest.skip("Set both TEST_DATABASE_URL and TEST_MIGRATION_DATABASE_URL for PostgreSQL tests")
    assert dsn and migration_dsn, "Both test database URLs are required"
    migrate(migration_dsn)
    migrate(migration_dsn)  # Re-running the migration command is safe.
    return dsn


@pytest.fixture
def login(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private_key.public_key()))
    monkeypatch.setattr(auth, "verifier", lambda: (ISSUER, AUDIENCE, CLIENT_ID, keys))

    def headers(subject, **overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "iss": ISSUER, "aud": AUDIENCE, "azp": CLIENT_ID, "sub": subject,
            "iat": now, "exp": now + timedelta(minutes=5), **overrides,
        }
        return {"Authorization": "Bearer " + jwt.encode(claims, private_key, algorithm="RS256")}

    return headers


@pytest.fixture
def client(database, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database)
    with TestClient(app) as client:
        yield client


def test_access_token_validation(login):
    # Rejected tokens never require a database connection.
    with TestClient(app) as client:
        assert client.get("/api/v1/me").status_code == 401
        for overrides in (
            {"aud": "different-api"}, {"azp": "different-client"}, {"iss": "https://different.example/"},
            {"exp": 0}, {"gty": "client-credentials"}, {"sub": "service@clients"}, {"sub": ""},
        ):
            response = client.get("/api/v1/me", headers=login("synthetic-user", **overrides))
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
        assert client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def create_organization(client, headers, name):
    response = client.post("/api/v1/organizations", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_assessment(client, headers, org, title):
    response = client.post(
        "/api/v1/assessments", params={"organization_id": org}, headers=headers, json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_two_organizations_are_isolated(client, login):
    alice = login(f"alice-{uuid4()}")
    bob = login(f"bob-{uuid4()}")
    org_a = create_organization(client, alice, "Synthetic A")
    org_b = create_organization(client, bob, "Synthetic B")
    item_a = create_assessment(client, alice, org_a, "Synthetic assessment A")
    item_b = create_assessment(client, bob, org_b, "Synthetic assessment B")
    root = "/api/v1/assessments"
    for outsider, own_org, foreign_org, own_item, foreign_item in (
        (alice, org_a, org_b, item_a, item_b),
        (bob, org_b, org_a, item_b, item_a),
    ):
        assert [o["id"] for o in client.get("/api/v1/organizations", headers=outsider).json()] == [own_org]
        scope = {"organization_id": own_org}
        assert [a["id"] for a in client.get(root, params=scope, headers=outsider).json()] == [own_item]
        for org in (own_org, foreign_org):
            params = {"organization_id": org}
            target = f"{root}/{foreign_item}"
            assert client.get(target, params=params, headers=outsider).status_code == 404
            assert client.patch(target, params=params, headers=outsider, json={"title": "Denied"}).status_code == 404
        foreign_scope = {"organization_id": foreign_org}
        assert client.get(root, params=foreign_scope, headers=outsider).status_code == 404
        assert client.post(root, params=foreign_scope, headers=outsider, json={"title": "Denied"}).status_code == 404
        assert client.post(root, params=scope, headers=outsider,
                           json={"title": "Denied", "organization_id": foreign_org}).status_code == 422
        assert client.get(f"/api/v1/organizations/{foreign_org}/members", headers=outsider).status_code == 404
        assert client.patch(f"/api/v1/organizations/{foreign_org}", headers=outsider,
                            json={"name": "Denied"}).status_code == 404

    updated = client.patch(f"{root}/{item_a}", params={"organization_id": org_a}, headers=alice,
                           json={"title": "Edited", "status": "archived"})
    assert updated.status_code == 200
    assert (updated.json()["title"], updated.json()["status"]) == ("Edited", "archived")


def test_owner_manages_members_and_revokes_access(client, login):
    owner = login(f"owner-{uuid4()}")
    member = login(f"member-{uuid4()}")
    member_id = client.get("/api/v1/me", headers=member).json()["id"]
    assert client.get("/api/v1/me", headers=member).json()["id"] == member_id
    org = create_organization(client, owner, "Synthetic team")
    path = f"/api/v1/organizations/{org}/members"
    assert client.post(path, headers=owner, json={"user_id": str(uuid4())}).status_code == 404
    assert client.post(path, headers=owner, json={"user_id": member_id}).status_code == 201
    assert client.post(path, headers=owner, json={"user_id": member_id}).status_code == 409
    assert client.get(path, headers=member).status_code == 403
    assert client.post(path, headers=member, json={"user_id": str(uuid4())}).status_code == 403
    assert client.patch(f"/api/v1/organizations/{org}", headers=member, json={"name": "Denied"}).status_code == 403
    assert client.patch(f"/api/v1/organizations/{org}", headers=owner, json={"name": "Renamed"}).status_code == 200
    item = create_assessment(client, member, org, "Member draft")
    owner_id = client.get("/api/v1/me", headers=owner).json()["id"]
    assert client.delete(f"{path}/{owner_id}", headers=owner).status_code == 404
    assert client.delete(f"{path}/{member_id}", headers=owner).status_code == 204
    target = f"/api/v1/assessments/{item}"
    assert client.get(target, params={"organization_id": org}, headers=member).status_code == 404
    assert client.get(target, params={"organization_id": org}, headers=owner).status_code == 200


def test_rls_blocks_queries_without_tenant_predicates(database, client, login):
    subject = f"actor-{uuid4()}"
    alice = login(subject)
    bob = login(f"other-{uuid4()}")
    org_a = create_organization(client, alice, "RLS A")
    org_b = create_organization(client, bob, "RLS B")
    item_a = create_assessment(client, alice, org_a, "RLS assessment A")
    item_b = create_assessment(client, bob, org_b, "RLS assessment B")

    with psycopg.connect(database, autocommit=True) as conn:
        assert conn.execute("SELECT id FROM assurance.assessments").fetchall() == []
        with conn.transaction():
            set_actor(conn, Identity(ISSUER, subject))
            assert conn.execute("SELECT id FROM assurance.assessments").fetchall() == []
            set_tenant(conn, UUID(org_a))
            assert conn.execute("SELECT id FROM assurance.assessments").fetchall() == [(UUID(item_a),)]
            assert conn.execute("UPDATE assurance.assessments SET title = 'Denied' WHERE id = %s",
                                (item_b,)).rowcount == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute("""
                    INSERT INTO assurance.assessments (organization_id, title, created_by)
                    VALUES (%s, 'Denied', assurance.actor_id())
                """, (org_b,))
            set_tenant(conn, UUID(org_b))
            assert conn.execute("SELECT id FROM assurance.organizations").fetchall() == []
            assert conn.execute("SELECT user_id FROM assurance.memberships").fetchall() == []
            assert conn.execute("SELECT id FROM assurance.assessments").fetchall() == []
        assert conn.execute("SELECT id FROM assurance.assessments").fetchall() == []
        assert conn.execute("SELECT id FROM assurance.users").fetchall() == []
