from collections.abc import Iterator
import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
import psycopg
from psycopg.rows import dict_row

from .auth import Identity, authenticate


def set_actor(conn: psycopg.Connection, identity: Identity) -> None:
    conn.execute(
        "SELECT set_config('assurance.issuer', %s, true), set_config('assurance.subject', %s, true)",
        (identity.issuer, identity.subject),
    )


def set_tenant(conn: psycopg.Connection, organization_id: UUID) -> None:
    conn.execute("SELECT set_config('assurance.organization_id', %s, true)", (str(organization_id),))


def transaction(
    identity: Annotated[Identity, Depends(authenticate)],
) -> Iterator[psycopg.Connection]:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise HTTPException(503, "Database is not configured")
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        # Never accept a migration or privileged connection as the web runtime.
        role = conn.execute("""
            SELECT current_user = 'assurance_app'
                AND session_user = current_user
                AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole
                AND NOT EXISTS (
                    SELECT FROM pg_catalog.pg_auth_members WHERE member = pg_roles.oid
                )
                AND NOT EXISTS (
                    SELECT FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'assurance' AND c.relowner = pg_roles.oid
                ) AS safe
            FROM pg_catalog.pg_roles WHERE rolname = current_user
        """).fetchone()
        if not role["safe"]:
            raise HTTPException(503, "Unsafe database role")
        set_actor(conn, identity)
        yield conn


Database = Annotated[psycopg.Connection, Depends(transaction, scope="function")]


def provision_user(conn: psycopg.Connection, identity: Identity) -> UUID:
    conn.execute(
        "INSERT INTO assurance.users (issuer, subject) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (identity.issuer, identity.subject),
    )
    return conn.execute(
        "SELECT id FROM assurance.users WHERE issuer = %s AND subject = %s",
        (identity.issuer, identity.subject),
    ).fetchone()["id"]
