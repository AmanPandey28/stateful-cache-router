from typing import List, Dict, Set, Optional, Tuple
import threading
import logging
logger = logging.getLogger("Router")
import time

class PrefixTreeNode:
    """Node in a prefix tree for block-based routing."""
    def __init__(self):
        self.children: Dict[str, 'PrefixTreeNode'] = {}
        self.workers: Set[str] = set()  # Workers that have this prefix


class GlobalCacheMap:
    def __init__(self):
        # Map: prefix_hash -> Set[worker_id] (for backward compatibility)
        self._map: Dict[str, Set[str]] = {}
        # Map: worker_id -> Set[prefix_hash] (Reverse Index for O(1) sync)
        self._worker_to_hashes: Dict[str, Set[str]] = {}
        # Map: worker_id -> List[block_hash] (ordered block sequences for prefix matching)
        self._worker_block_sequences: Dict[str, List[str]] = {}
        # Prefix tree root for longest prefix matching
        self._prefix_tree_root = PrefixTreeNode()
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
    
    def update_block_sequence(self, worker_id: str, block_hashes: List[str]):
        """
        Update the block sequence for a worker. This builds the prefix tree.
        block_hashes should be an ordered list of block hashes.
        """
        with self._lock:
            # Store the full sequence
            self._worker_block_sequences[worker_id] = block_hashes.copy()
            
            # Remove old entries from prefix tree
            self._remove_worker_from_tree(worker_id)
            
            # Add new entries to prefix tree
            node = self._prefix_tree_root
            for block_hash in block_hashes:
                if block_hash not in node.children:
                    node.children[block_hash] = PrefixTreeNode()
                node = node.children[block_hash]
                node.workers.add(worker_id)

    def evict(self, worker_id: str, prefix_hash: str):
        """Remove a prefix from a worker's cache record."""
        with self._lock:
            if prefix_hash in self._map:
                self._map[prefix_hash].discard(worker_id)
                if not self._map[prefix_hash]:
                    del self._map[prefix_hash]
            
            if worker_id in self._worker_to_hashes:
                self._worker_to_hashes[worker_id].discard(prefix_hash)
            
            # Remove from prefix tree
            self._remove_worker_from_tree(worker_id)
    
    def _remove_worker_from_tree(self, worker_id: str):
        """Remove a worker from the prefix tree."""
        if worker_id not in self._worker_block_sequences:
            return
        
        block_hashes = self._worker_block_sequences[worker_id]
        node = self._prefix_tree_root
        
        for block_hash in block_hashes:
            if block_hash in node.children:
                node = node.children[block_hash]
                node.workers.discard(worker_id)
                
                # Clean up empty nodes (optional optimization)
                if not node.workers and not node.children:
                    # Can be removed, but we'll leave it for simplicity
                    pass

    def sync_worker_state(self, worker_id: str, active_hashes: List[str]):
        """
        Reconcile the worker's cache state.
        Replace the router's view of this worker's cache with the provided list.
        active_hashes should be an ordered list of block hashes for prefix matching.
        """
        with self._lock:
            logger.info(f"[SYNC DEBUG] Starting sync for {worker_id}, active_hashes={len(active_hashes)}")
            
            # 1. Remove worker from all current entries using Reverse Index
            if worker_id in self._worker_to_hashes:
                current_hashes = list(self._worker_to_hashes[worker_id])
                for h in current_hashes:
                    if h in self._map:
                        self._map[h].discard(worker_id)
                        if not self._map[h]:
                            del self._map[h]
                self._worker_to_hashes[worker_id].clear()
            
            # 2. Remove from prefix tree
            self._remove_worker_from_tree(worker_id)
            
            # 3. Add worker to new active entries (as block sequence)
            if active_hashes:
                # Update block sequence for prefix matching
                self.update_block_sequence(worker_id, active_hashes)
                
                # Also update the hash map for backward compatibility
                for h in active_hashes:
                    if h not in self._map:
                        self._map[h] = set()
                    self._map[h].add(worker_id)
                    
                    if worker_id not in self._worker_to_hashes:
                        self._worker_to_hashes[worker_id] = set()
                    self._worker_to_hashes[worker_id].add(h)
            
            # Update liveness
            self._worker_load[worker_id] = self._worker_load.get(worker_id, 0)

    def get_workers_for_prefix(self, prefix_hash: str) -> List[str]:
        """Get list of workers that have the prefix cached (backward compatibility)."""
        with self._lock:
            return list(self._map.get(prefix_hash, []))
    
    def find_longest_prefix_match(self, block_hashes: List[str]) -> Tuple[Optional[str], int]:
        """
        Find the worker with the longest prefix match for the given block sequence.
        Returns (worker_id, match_length) where match_length is the number of matching blocks.
        If no match, returns (None, 0).
        """
        with self._lock:
            best_worker = None
            best_length = 0
            
            node = self._prefix_tree_root
            matched_length = 0
            
            # Traverse the tree following the block sequence
            for block_hash in block_hashes:
                if block_hash not in node.children:
                    break
                
                node = node.children[block_hash]
                matched_length += 1
                
                # If this node has workers, update best match
                if node.workers:
                    # Among workers at this level, pick the least loaded
                    candidates = list(node.workers)
                    if candidates:
                        best_worker = self._get_least_loaded_from_list(candidates)
                        best_length = matched_length
            
            return (best_worker, best_length)
    
    def _get_least_loaded_from_list(self, candidates: List[str]) -> Optional[str]:
        """Get least loaded worker from a list of candidates."""
        if not candidates:
            return None
        
        valid_candidates = [w for w in candidates if w in self._worker_load]
        if not valid_candidates:
            return candidates[0]  # Fallback
        
        return min(valid_candidates, key=lambda w: self._worker_load[w])

    def update_load(self, worker_id: str, current_load: int):
        """Update the load metric for a worker."""
        with self._lock:
            self._worker_load[worker_id] = current_load

    def get_least_loaded_worker(self, candidates: List[str] = None) -> str:
        """
        Return the worker with the lowest load.
        If candidates is None, consider all known workers.
        Uses round-robin tie-breaking when loads are equal.
        """
        with self._lock:
            if not self._worker_load:
                return None
            
            pool = candidates if candidates else list(self._worker_load.keys())
            # Filter pool to only include known workers
            valid_pool = [w for w in pool if w in self._worker_load]
            
            if not valid_pool:
                # Fallback if candidates are not in our load map yet
                return candidates[0] if candidates else None

            # Find minimum load
            min_load = min(self._worker_load[w] for w in valid_pool)
            
            # Get all workers with minimum load
            min_load_workers = [w for w in valid_pool if self._worker_load[w] == min_load]
            
            # If tie, use round-robin (cycle through tied workers)
            if not hasattr(self, '_least_loaded_rr_index'):
                self._least_loaded_rr_index = {}
            
            # Use a key based on the set of tied workers for round-robin
            tie_key = tuple(sorted(min_load_workers))
            if tie_key not in self._least_loaded_rr_index:
                self._least_loaded_rr_index[tie_key] = 0
            
            selected = min_load_workers[self._least_loaded_rr_index[tie_key] % len(min_load_workers)]
            self._least_loaded_rr_index[tie_key] += 1
            
            return selected
