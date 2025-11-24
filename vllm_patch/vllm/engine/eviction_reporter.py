import asyncio
import aiohttp
import logging
from typing import List, Deque
from collections import deque

logger = logging.getLogger("vllm.engine.eviction_reporter")

class EvictionReporter:
    def __init__(self, router_url: str, worker_id: str, report_interval: float = 0.1):
        self.router_url = router_url
        self.worker_id = worker_id
        self.report_interval = report_interval
        self.eviction_queue: Deque[str] = deque()
        self._running = False
        self._task = None

    def add_evicted_hash(self, prefix_hash: str):
        """Add a hash to the queue to be reported."""
        self.eviction_queue.append(prefix_hash)

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._report_loop())
        logger.info("EvictionReporter started.")

    async def stop(self):
        self._running = False
        if self._task:
            await self._task
        logger.info("EvictionReporter stopped.")

    async def _report_loop(self):
        async with aiohttp.ClientSession() as session:
            while self._running:
                await asyncio.sleep(self.report_interval)
                
                if not self.eviction_queue:
                    continue

                # Drain the queue
                batch = []
                while self.eviction_queue:
                    batch.append(self.eviction_queue.popleft())

                if not batch:
                    continue

                try:
                    payload = {
                        "worker_id": self.worker_id,
                        "evicted_hashes": batch
                    }
                    async with session.post(f"{self.router_url}/internal/eviction", json=payload) as resp:
                        if resp.status != 200:
                            logger.error(f"Failed to report evictions: {resp.status}")
                except Exception as e:
                    logger.error(f"Error reporting evictions: {e}")
