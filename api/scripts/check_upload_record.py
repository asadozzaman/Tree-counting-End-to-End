import os
import sys
import psycopg2

job_id = sys.argv[1]
asset_id = sys.argv[2]
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT id, project_id, status FROM jobs WHERE id = %s', (job_id,))
job = cur.fetchone()
cur.execute('SELECT id, project_id, job_id, kind, mime_type, size_bytes FROM assets WHERE id = %s', (asset_id,))
asset = cur.fetchone()
print('JOB_ROW', job)
print('ASSET_ROW', asset)
conn.close()
