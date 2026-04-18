import sqlite3
import os
import asyncio
from backend.database import engine, Base
from backend.models import EmailOutreach

def alter_email_outreach():
    db_path = "data/job_automater.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        try:
            cur.execute("ALTER TABLE email_outreach ADD COLUMN body TEXT")
            print("Added body to email_outreach")
        except sqlite3.OperationalError as e:
            print("body error:", e)
        conn.commit()
        conn.close()

if __name__ == "__main__":
    alter_email_outreach()
    print("Database updated!")
