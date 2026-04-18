import sqlite3
import os

db_path = "data/job_automater.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("UPDATE pending_jobs SET status='pending', attempts=0 WHERE status='failed'")
affected = cursor.rowcount
conn.commit()
conn.close()

print(f"Successfully reset {affected} failed jobs to pending.")
