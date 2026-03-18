import os
from pathlib import Path
import psycopg2


def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(database_url)


def ensure_migrations_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def applied_migrations(cur):
    cur.execute("SELECT name FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def apply_migration(cur, name: str, sql: str):
    cur.execute(sql)
    cur.execute("INSERT INTO schema_migrations(name) VALUES (%s)", (name,))


def main():
    migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
    files = sorted(p for p in migrations_dir.glob("*.sql"))

    with get_conn() as conn:
        with conn.cursor() as cur:
            ensure_migrations_table(cur)
            done = applied_migrations(cur)

            for file in files:
                if file.name in done:
                    print(f"SKIP {file.name}")
                    continue
                sql = file.read_text(encoding="utf-8")
                apply_migration(cur, file.name, sql)
                print(f"APPLIED {file.name}")


if __name__ == "__main__":
    main()
