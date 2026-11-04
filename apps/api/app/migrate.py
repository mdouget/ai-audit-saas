"""Apply checked-in PostgreSQL migrations using the separate migration role."""
import os
from pathlib import Path

import psycopg


def migrate(dsn: str) -> None:
    directory = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(912613490)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS assurance_migrations")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assurance_migrations.applied (
                filename text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        applied = {row[0] for row in conn.execute("SELECT filename FROM assurance_migrations.applied")}
        for path in sorted(directory.glob("[0-9]*.sql")):
            if path.name not in applied:
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO assurance_migrations.applied VALUES (%s)", (path.name,))


if __name__ == "__main__":
    migrate(os.environ["MIGRATION_DATABASE_URL"])
