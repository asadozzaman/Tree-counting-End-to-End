import os
import psycopg2


def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(database_url)


def main():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users(email, password_hash, full_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
                RETURNING id
                """,
                ("demo@tree-saas.local", "demo-hash", "Demo User"),
            )
            user_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO projects(user_id, name, description, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, "Demo Tree Inventory", "Seed project", "active"),
            )
            project_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO jobs(project_id, status, input_type)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (project_id, "done", "image"),
            )
            job_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO assets(project_id, job_id, kind, file_path, mime_type, size_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (project_id, job_id, "input", "seed/demo-image.jpg", "image/jpeg", 123456),
            )
            asset_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO detections(job_id, asset_id, class_id, class_name, x1, y1, x2, y2, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (job_id, asset_id, 0, "tree", 10.5, 20.0, 120.0, 220.0, 0.91),
            )

            cur.execute(
                """
                INSERT INTO job_metrics(job_id, project_id, tree_count, avg_confidence, duration_ms)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (job_id)
                DO UPDATE SET tree_count = EXCLUDED.tree_count,
                              avg_confidence = EXCLUDED.avg_confidence,
                              duration_ms = EXCLUDED.duration_ms
                """,
                (job_id, project_id, 1, 0.91, 87),
            )

            print(f"SEEDED user_id={user_id} project_id={project_id} job_id={job_id}")


if __name__ == "__main__":
    main()
