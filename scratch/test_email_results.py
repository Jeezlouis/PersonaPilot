import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import AsyncSessionLocal
from backend.models import Job
from backend.modules.mailer.email_extractor import extract_email_info
from sqlalchemy import select

async def run_test():
    print("--- [1] Checking Database for Extracted Emails ---")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Job).where(Job.contact_email.isnot(None)))
        jobs = res.scalars().all()
        print(f"Total jobs in DB with emails: {len(jobs)}")
        for j in jobs:
            print(f"  [OK] {j.title} @ {j.company}: {j.contact_email} ({j.contact_confidence})")

    print("\n--- [2] Testing Extraction Logic ---")
    test_desc = "We are looking for a developer. Send your CV to hello@futuretech.com for a quick response."
    email, confidence = extract_email_info(test_desc, "http://example.com/job", "FutureTech")
    
    if email == "hello@futuretech.com":
        print(f"SUCCESS: Extracted '{email}' from test description!")
    else:
        print(f"FAILED: Expected 'hello@futuretech.com', got '{email}'")

if __name__ == "__main__":
    asyncio.run(run_test())
