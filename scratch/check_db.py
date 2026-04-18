import sqlite3
import os

db_paths = ["data/job_automater.db", "job_automater.db"]

for db_path in db_paths:
    print(f"\n===== Checking {db_path} =====")
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        continue

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- Jobs Table ---")
    cursor.execute("SELECT id, title, status FROM jobs WHERE id = 612")
    row = cursor.fetchone()
    if row:
        print(f"Job 612: {row}")
    else:
        print("Job 612 not found in jobs table.")

    print("\n--- Pending Jobs Table ---")
    cursor.execute("SELECT id, status FROM pending_jobs WHERE id = 612")
    row = cursor.fetchone()
    if row:
        print(f"Pending Job 612: {row}")
    else:
        print("Job 612 not found in pending_jobs table.")

    print("\n--- Recent Jobs ---")
    cursor.execute("SELECT id, title, status FROM jobs ORDER BY id DESC LIMIT 5")
    for row in cursor.fetchall():
        print(row)

    conn.close()
