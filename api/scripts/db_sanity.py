import os
import psycopg2


def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(database_url)


def fetch_one(cur, sql):
    cur.execute(sql)
    return cur.fetchone()[0]


def main():
    with get_conn() as conn:
        with conn.cursor() as cur:
            table_counts = {}
            for table in ["users", "projects", "jobs", "assets", "detections", "job_metrics"]:
                table_counts[table] = fetch_one(cur, f"SELECT COUNT(*) FROM {table}")

            fk_orphans = {
                "projects_user_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM projects p
                    LEFT JOIN users u ON u.id = p.user_id
                    WHERE u.id IS NULL
                    """,
                ),
                "jobs_project_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM jobs j
                    LEFT JOIN projects p ON p.id = j.project_id
                    WHERE p.id IS NULL
                    """,
                ),
                "assets_project_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM assets a
                    LEFT JOIN projects p ON p.id = a.project_id
                    WHERE p.id IS NULL
                    """,
                ),
                "assets_job_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM assets a
                    LEFT JOIN jobs j ON j.id = a.job_id
                    WHERE a.job_id IS NOT NULL AND j.id IS NULL
                    """,
                ),
                "detections_job_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM detections d
                    LEFT JOIN jobs j ON j.id = d.job_id
                    WHERE j.id IS NULL
                    """,
                ),
                "job_metrics_job_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM job_metrics m
                    LEFT JOIN jobs j ON j.id = m.job_id
                    WHERE j.id IS NULL
                    """,
                ),
                "job_metrics_project_orphans": fetch_one(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM job_metrics m
                    LEFT JOIN projects p ON p.id = m.project_id
                    WHERE p.id IS NULL
                    """,
                ),
            }

            print("ROW_COUNTS", table_counts)
            print("FK_ORPHANS", fk_orphans)


if __name__ == "__main__":
    main()
