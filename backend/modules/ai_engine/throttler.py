import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class GeminiThrottler:
    """
    Rate limiter for Gemini Free Tier (15 RPM).
    Ensures at least 4 seconds between requests and uses a semaphore.
    """
    def __init__(self, rpm=10): # Set to 10 to be very safe
        self.semaphore = asyncio.Semaphore(1) # Sequential to avoid burst conflicts
        self.last_call = 0
        self.delay = 60.0 / rpm

    async def throttle(self):
        async with self.semaphore:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.delay:
                wait_time = self.delay - elapsed
                logger.debug(f"[Throttler] Waiting {wait_time:.2f}s for Gemini RPM limit...")
                await asyncio.sleep(wait_time)
            
            self.last_call = time.time()

# Global instance
gemini_throttler = GeminiThrottler(rpm=12) # 12 RPM = 5s per request
