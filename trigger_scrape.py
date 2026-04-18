import asyncio
import logging
from backend.scheduler import run_scrape_and_score

logging.basicConfig(level=logging.INFO)

async def main():
    await run_scrape_and_score()

if __name__ == "__main__":
    asyncio.run(main())
