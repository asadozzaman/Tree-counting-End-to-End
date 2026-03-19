import os
import sys
import psycopg2

job_id = sys.argv[1]
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT status, error_message FROM jobs WHERE id = %s', (job_id,))
job = cur.fetchone()
cur.execute('SELECT COUNT(*) FROM detections WHERE job_id = %s', (job_id,))
d_count = cur.fetchone()[0]
cur.execute('SELECT tree_count, avg_confidence, duration_ms FROM job_metrics WHERE job_id = %s', (job_id,))
metrics = cur.fetchone()
print('JOB', job)
print('DETECTIONS', d_count)
print('METRICS', metrics)
conn.close()
