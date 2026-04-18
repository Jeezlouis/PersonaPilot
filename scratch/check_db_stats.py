
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta

async def check_db():
    conn = sqlite3.connect('./data/job_automater.db')
    cursor = conn.cursor()
    
    # Total jobs
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total = cursor.fetchone()[0]
    print(f"Total jobs: {total}")
    
    # Status breakdown
    cursor.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
    print("Status breakdown:")
    for status, count in cursor.fetchall():
        print(f"  {status}: {count}")
    
    # Jobs found today
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE found_at >= ?", (today,))
    found_today = cursor.fetchone()[0]
    print(f"Jobs found today: {found_today}")
    
    # Score distribution for new/reviewed jobs
    cursor.execute("SELECT match_score FROM jobs WHERE status != 'skipped' ORDER BY match_score DESC LIMIT 10")
    top_scores = cursor.fetchall()
    print("Top 10 scores (non-skipped):")
    for s in top_scores:
        print(f"  {s[0]}")
        
    cursor.execute("SELECT AVG(match_score), MAX(match_score), MIN(match_score) FROM jobs WHERE status != 'skipped'")
    avg_max_min = cursor.fetchone()
    print(f"Stats (non-skipped): Avg={avg_max_min[0]}, Max={avg_max_min[1]}, Min={avg_max_min[2]}")

    # Check skipped for seniority reasons
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'skipped'")
    skipped_count = cursor.fetchone()[0]
    print(f"Skipped jobs: {skipped_count}")

    conn.close()

if __name__ == "__main__":
    asyncio.run(check_db())
