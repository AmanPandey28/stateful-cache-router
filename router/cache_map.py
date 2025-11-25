from typing import List, Dict, Set
import threading
import logging
logger = logging.getLogger("Router")
import time

class GlobalCacheMap:
    def __init__(self):
        # Map: prefix_hash -> Set[worker_id]
        self._map: Dict[str, Set[str]] = {}
        # Map: worker_id -> Set[prefix_hash] (Reverse Index for O(1) sync)
        self._worker_to_hashes: Dict[str, Set[str]] = {}
        # Map: worker_id -> last_heartbeat_timestamp
        self._worker_load: Dict[str, int] = {} 
        self._lock = threading.RLock()

    def update(self, worker_id: str, prefix_hash: str):
        """Register that a worker has a specific prefix cached."""
        with self._lock:
            if prefix_hash not in self._map:
                self._map[prefix_hash] = set()
            self._map[prefix_hash].add(worker_id)
            
            if worker_id not in self._worker_to_hashes:
                self._worker_to_hashes[worker_id] = set()
            self._worker_to_hashes[worker_id].add(prefix_hash)
            
            # Update worker "load" or liveness (simplified)
            self._worker_load[worker_id] = self._worker_load.get(worker_id, 0)

    def evict(self, worker_id: str, prefix_hash: str):
        """Remove a prefix from a worker's cache record."""
        with self._lock:
            if prefix_hash in self._map:
                self._map[prefix_hash].discard(worker_id)
                if not self._map[prefix_hash]:
                    del self._map[prefix_hash]
            
            if worker_id in self._worker_to_hashes:
                self._worker_to_hashes[worker_id].discard(prefix_hash)

    def sync_worker_state(self, worker_id: str, active_hashes: List[str]):
        """
        Reconcile the worker's cache state.
        Replace the router's view of this worker's cache with the provided list.
        """
        with self._lock:
            logger.info(f"[SYNC DEBUG] Starting sync for {worker_id}, active_hashes={len(active_hashes)}")
            logger.info(f"[SYNC DEBUG] Current map state: {dict(self._map)}")
            
            # 1. Remove worker from all current entries using Reverse Index
            # This is now O(M) where M is the number of hashes THIS worker has, not total hashes.
            if worker_id in self._worker_to_hashes:
                current_hashes = list(self._worker_to_hashes[worker_id])
                logger.info(f"[SYNC DEBUG] Clearing {len(current_hashes)} old hashes for {worker_id}: {current_hashes}")
                for h in current_hashes:
                    if h in self._map:
                        self._map[h].discard(worker_id)
                        if not self._map[h]:
                            del self._map[h]
                            logger.info(f"[SYNC DEBUG] Deleted hash {h[:8]}... from map (no workers left)")
                # Clear reverse map for this worker
                self._worker_to_hashes[worker_id].clear()
            else:
                logger.info(f"[SYNC DEBUG] Worker {worker_id} not in reverse map")
            
            # 2. Add worker to new active entries
            for h in active_hashes:
                if h not in self._map:
                    self._map[h] = set()
                self._map[h].add(worker_id)
                
                if worker_id not in self._worker_to_hashes:
                    self._worker_to_hashes[worker_id] = set()
                self._worker_to_hashes[worker_id].add(h)
            
            logger.info(f"[SYNC DEBUG] After sync, map state: {dict(self._map)}")
            
            # Update liveness
            self._worker_load[worker_id] = self._worker_load.get(worker_id, 0)

    def get_workers_for_prefix(self, prefix_hash: str) -> List[str]:
        """Get list of workers that have the prefix cached."""
        with self._lock:
            return list(self._map.get(prefix_hash, []))

    def update_load(self, worker_id: str, current_load: int):
        """Update the load metric for a worker."""
        with self._lock:
            self._worker_load[worker_id] = current_load

    def get_least_loaded_worker(self, candidates: List[str] = None) -> str:
        """
        Return the worker with the lowest load.
        If candidates is None, consider all known workers.
        """
        with self._lock:
            if not self._worker_load:
                return None
            
            pool = candidates if candidates else self._worker_load.keys()
            # Filter pool to only include known workers
            valid_pool = [w for w in pool if w in self._worker_load]
            
            if not valid_pool:
                # Fallback if candidates are not in our load map yet
                return candidates[0] if candidates else None

            return min(valid_pool, key=lambda w: self._worker_load[w])
