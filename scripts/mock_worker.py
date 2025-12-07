import asyncio
import aiohttp
import logging
import random
import time
import heapq
from collections import defaultdict, OrderedDict
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from router.tokenizer_utils import TokenizerUtils, BLOCK_SIZE

# Try to import lightweight model for token generation
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    LIGHTWEIGHT_MODEL_AVAILABLE = True
except ImportError:
    torch = None
    LIGHTWEIGHT_MODEL_AVAILABLE = False
    logging.warning("transformers/torch not available, using dummy token generation")

ROUTER_URL = "http://localhost:8000"
WORKER_ID = f"worker-{random.randint(1000, 9999)}"

# Model configuration: Llama 2 13B on A100 40GB
MODEL_LAYERS = 40
MODEL_HEADS = 40
MODEL_DIM = 128
FP16_BYTES = 2
BLOCKS_PER_GPU = 924  # (40GB - 26GB model - 11.3GB overhead) / 13,107,200 bytes per block

# Latency constants (realistic for A100 with Llama 2 13B)
# Prefill latency: depends on number of blocks to compute
# Formula: base_latency + (blocks_to_compute * latency_per_block)
PREFILL_BASE_MS = 5.0  # Base overhead
PREFILL_PER_BLOCK_MS = 2.5  # ms per block for prefill computation

# Decode latency: per token
DECODE_PER_TOKEN_MS = 15.0  # ms per token for decode (realistic for A100)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockWorker")


@dataclass
class BlockInfo:
    """Represents a cached block with reference counting."""
    block_hash: str
    ref_count: int = 0
    last_used: float = field(default_factory=time.time)
    evictable: bool = False
    sequence_id: Optional[str] = None  # Which request sequence this block belongs to
    block_index: int = 0  # Position in sequence (for tie-breaking)


@dataclass
class Task:
    """Represents an inference task."""
    request_id: str
    prompt: str
    max_tokens: int
    block_hashes: List[str]  # All block hashes for this request
    cached_blocks: Set[str]  # Which blocks are already cached
    created_at: float = field(default_factory=time.time)
    
    # Task state
    stage: str = "prefill"  # "prefill" or "decode"
    prefill_blocks_to_compute: int = 0
    decode_tokens_remaining: int = 0
    current_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    # For tracking
    prompt_tokens: int = 0
    generated_tokens: int = 0


class BlockCache:
    """Manages block-based cache with reference counting and eviction."""
    
    def __init__(self, max_blocks: int = BLOCKS_PER_GPU):
        self.max_blocks = max_blocks
        # Map: block_hash -> BlockInfo
        self.blocks: Dict[str, BlockInfo] = {}
        # Priority queue for evictable blocks: (last_used, block_index, block_hash)
        # Lower priority = older/more evictable
        self.evictable_queue: List[Tuple[float, int, str]] = []
        self.sequence_blocks: Dict[str, List[str]] = {}  # sequence_id -> list of block_hashes
        # Track all active sequences for sync
        self.active_sequences: List[List[str]] = []  # List of block sequences
    
    def get_cached_blocks(self, block_hashes: List[str]) -> Set[str]:
        """Check which blocks are already cached."""
        return {h for h in block_hashes if h in self.blocks}
    
    def allocate_blocks(self, block_hashes: List[str], sequence_id: str) -> Tuple[Set[str], List[str]]:
        """
        Allocate blocks for a sequence. Returns (cached_blocks, blocks_to_allocate).
        Updates reference counts for cached blocks.
        """
        cached = set()
        to_allocate = []
        
        for i, block_hash in enumerate(block_hashes):
            if block_hash in self.blocks:
                # Block exists, increment ref count
                block_info = self.blocks[block_hash]
                block_info.ref_count += 1
                block_info.last_used = time.time()
                block_info.evictable = False
                # Remove from evictable queue if present
                self._remove_from_evictable(block_hash)
                cached.add(block_hash)
            else:
                # Need to allocate new block
                to_allocate.append(block_hash)
        
        # Allocate new blocks (may need eviction)
        for block_hash in to_allocate:
            if len(self.blocks) >= self.max_blocks:
                evicted = self._evict_oldest_block()
                if evicted:
                    logger.info(f"🗑️  Evicted block {evicted[:8]}... to make room")
            
            # Create new block
            block_info = BlockInfo(
                block_hash=block_hash,
                ref_count=1,
                last_used=time.time(),
                evictable=False,
                sequence_id=sequence_id,
                block_index=len(to_allocate) - to_allocate.index(block_hash)
            )
            self.blocks[block_hash] = block_info
        
        # Track blocks for this sequence
        self.sequence_blocks[sequence_id] = block_hashes
        
        # Add to active sequences for sync (if not already present)
        # Use a copy to avoid reference issues
        block_hashes_copy = block_hashes.copy()
        if block_hashes_copy not in self.active_sequences:
            self.active_sequences.append(block_hashes_copy)
            logger.info(f"📦 Added sequence {sequence_id} with {len(block_hashes)} blocks to cache")
        
        return cached, to_allocate
    
    def mark_sequence_complete(self, sequence_id: str):
        """Mark all blocks for a sequence as evictable."""
        if sequence_id not in self.sequence_blocks:
            return
        
        for block_hash in self.sequence_blocks[sequence_id]:
            if block_hash in self.blocks:
                block_info = self.blocks[block_hash]
                block_info.ref_count -= 1
                if block_info.ref_count == 0:
                    block_info.evictable = True
                    # Add to evictable queue
                    heapq.heappush(
                        self.evictable_queue,
                        (block_info.last_used, block_info.block_index, block_hash)
                    )
        
        # Don't remove from active_sequences yet - blocks are still cached
        # They'll be removed when actually evicted
        # This allows the router to still see them for prefix matching
        # until they're actually freed from memory
        
        del self.sequence_blocks[sequence_id]
    
    def _evict_oldest_block(self):
        """Evict the oldest evictable block. If tie, evict latest in sequence."""
        while self.evictable_queue:
            last_used, block_index, block_hash = heapq.heappop(self.evictable_queue)
            
            if block_hash not in self.blocks:
                continue  # Already evicted
            
            block_info = self.blocks[block_hash]
            if not block_info.evictable or block_info.ref_count > 0:
                continue  # No longer evictable or still in use
            
            # Evict this block
            del self.blocks[block_hash]
            
            # Remove sequences from active_sequences if all their blocks are evicted
            sequences_to_remove = []
            for seq in self.active_sequences:
                if block_hash in seq:
                    # Check if any blocks from this sequence are still cached
                    if not any(bh in self.blocks for bh in seq):
                        sequences_to_remove.append(seq)
            
            for seq in sequences_to_remove:
                if seq in self.active_sequences:
                    self.active_sequences.remove(seq)
            
            return block_hash
        
        # No evictable blocks, evict oldest by last_used (shouldn't happen often)
        if self.blocks:
            oldest = min(self.blocks.values(), key=lambda b: b.last_used)
            evicted_hash = oldest.block_hash
            del self.blocks[evicted_hash]
            
            # Clean up sequences
            sequences_to_remove = []
            for seq in self.active_sequences:
                if evicted_hash in seq:
                    if not any(bh in self.blocks for bh in seq):
                        sequences_to_remove.append(seq)
            
            for seq in sequences_to_remove:
                if seq in self.active_sequences:
                    self.active_sequences.remove(seq)
            
            return evicted_hash
        
        return None
    
    def _remove_from_evictable(self, block_hash: str):
        """Remove a block from evictable queue (it's being used again)."""
        # Rebuild queue without this block (simple approach)
        new_queue = [
            (last_used, idx, h) 
            for last_used, idx, h in self.evictable_queue 
            if h != block_hash
        ]
        heapq.heapify(new_queue)
        self.evictable_queue = new_queue
    
    def get_all_block_hashes(self) -> Set[str]:
        """Get all currently cached block hashes."""
        return set(self.blocks.keys())
    
    def get_all_block_sequences(self) -> List[List[str]]:
        """Get all active block sequences for sync."""
        # Return all sequences that still have blocks in cache
        # This includes evictable blocks (they're still cached until evicted)
        active_seqs = []
        seen_hashes = set()
        
        # Check active_sequences first
        for seq in self.active_sequences:
            # Check if any blocks from this sequence are still in cache
            cached_blocks_in_seq = [bh for bh in seq if bh in self.blocks]
            if cached_blocks_in_seq:
                # Use the full sequence (even if some blocks are evicted, we want the order)
                active_seqs.append(seq.copy())
                seen_hashes.update(seq)
        
        # Also include sequences from sequence_blocks that might not be in active_sequences
        for sequence_id, block_hashes in self.sequence_blocks.items():
            # Check if this sequence has any cached blocks
            cached_blocks_in_seq = [bh for bh in block_hashes if bh in self.blocks]
            if cached_blocks_in_seq:
                # Check if we haven't already added this sequence (by comparing block hashes)
                seq_set = set(block_hashes)
                if not any(set(s) == seq_set for s in active_seqs):
                    active_seqs.append(block_hashes.copy())
                    seen_hashes.update(block_hashes)
        
        return active_seqs


class LightweightModel:
    """Lightweight CPU model for token generation."""
    
    def __init__(self):
        self.tokenizer = None
        self.model = None
        if LIGHTWEIGHT_MODEL_AVAILABLE:
            try:
                # Use a very small model for fast CPU inference
                model_name = "gpt2"  # Small and fast
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForCausalLM.from_pretrained(model_name)
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                logger.info("Loaded lightweight model for token generation")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}, using dummy generation")
                self.tokenizer = None
                self.model = None
    
    def generate_tokens(self, prompt: str, max_tokens: int) -> Tuple[List[int], int]:
        """
        Generate tokens for the prompt. Returns (token_ids, num_tokens_to_generate).
        This simulates what the actual LLM would generate.
        """
        if self.model is None or self.tokenizer is None:
            # Dummy generation: just return prompt tokens + estimate output
            prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
            return list(range(int(prompt_tokens))), max_tokens
        
        try:
            # Tokenize prompt
            inputs = self.tokenizer(prompt, return_tensors="pt")
            prompt_token_ids = inputs["input_ids"][0].tolist()
            
            # Generate (with very limited generation for speed)
            if torch is not None:
                with torch.no_grad():
                    outputs = self.model.generate(
                        inputs["input_ids"],
                        max_new_tokens=min(max_tokens, 50),  # Limit for speed
                        do_sample=False,
                        pad_token_id=self.tokenizer.eos_token_id
                    )
                generated_token_ids = outputs[0][len(prompt_token_ids):].tolist()
            else:
                # Fallback if torch not available
                generated_token_ids = []
            
            num_tokens = len(generated_token_ids) if generated_token_ids else max_tokens
            
            return prompt_token_ids + generated_token_ids, num_tokens
        except Exception as e:
            logger.warning(f"Generation failed: {e}, using dummy")
            prompt_tokens = len(prompt.split()) * 1.3
            return list(range(int(prompt_tokens))), max_tokens


class WorkerState:
    """Manages worker state including cache and tasks."""
    
    def __init__(self):
        self.cache = BlockCache()
        self.tasks: List[Task] = []
        self.lightweight_model = LightweightModel()
        self.tokenizer_utils = TokenizerUtils()
        self.request_counter = 0
    
    def add_task(self, prompt: str, max_tokens: int) -> Task:
        """Add a new inference task."""
        self.request_counter += 1
        request_id = f"req-{self.request_counter}"
        
        # Compute block hashes for the prompt
        block_hashes = self.tokenizer_utils.compute_block_hashes(prompt)
        prompt_tokens = self.tokenizer_utils.get_num_tokens(prompt)
        
        # Check which blocks are cached
        cached_blocks = self.cache.get_cached_blocks(block_hashes)
        
        # Allocate blocks (updates ref counts)
        cached_after_alloc, blocks_to_allocate = self.cache.allocate_blocks(block_hashes, request_id)
        
        # Determine how many blocks need computation
        # If some blocks are missing, we need to recompute from the first missing block
        blocks_to_compute = 0
        if blocks_to_allocate:
            # Find first missing block
            first_missing_idx = block_hashes.index(blocks_to_allocate[0])
            blocks_to_compute = len(block_hashes) - first_missing_idx
        else:
            # All cached, minimal prefill
            blocks_to_compute = 0
        
        # Generate tokens to determine decode length
        _, num_decode_tokens = self.lightweight_model.generate_tokens(prompt, max_tokens)
        
        task = Task(
            request_id=request_id,
            prompt=prompt,
            max_tokens=max_tokens,
            block_hashes=block_hashes,
            cached_blocks=cached_after_alloc,
            prompt_tokens=prompt_tokens,
            decode_tokens_remaining=num_decode_tokens,
            prefill_blocks_to_compute=blocks_to_compute
        )
        
        # Calculate prefill latency
        if blocks_to_compute > 0:
            task.current_latency_ms = PREFILL_BASE_MS + (blocks_to_compute * PREFILL_PER_BLOCK_MS)
        else:
            # All cached, minimal prefill
            task.current_latency_ms = PREFILL_BASE_MS * 0.1
        
        self.tasks.append(task)
        return task
    
    def process_tasks(self, delta_time_ms: float = 1.0):
        """Process tasks, advancing their latency counters."""
        completed_tasks = []
        
        for task in self.tasks[:]:
            if task.stage == "prefill":
                task.current_latency_ms -= delta_time_ms
                if task.current_latency_ms <= 0:
                    # Prefill complete, move to decode
                    task.stage = "decode"
                    # Calculate decode latency
                    if task.decode_tokens_remaining > 0:
                        # Check if decode tokens might be out of cache
                        # For simplicity, we assume decode tokens are always computed
                        # In reality, if decode tokens are out of cache, treat as prefill
                        task.current_latency_ms = task.decode_tokens_remaining * DECODE_PER_TOKEN_MS
                    else:
                        task.current_latency_ms = 0
            
            elif task.stage == "decode":
                task.current_latency_ms -= delta_time_ms
                # Generate tokens incrementally
                if task.current_latency_ms > 0:
                    # Simulate token generation progress
                    tokens_generated = int((task.decode_tokens_remaining * DECODE_PER_TOKEN_MS - task.current_latency_ms) / DECODE_PER_TOKEN_MS)
                    task.generated_tokens = min(tokens_generated, task.decode_tokens_remaining)
                
                if task.current_latency_ms <= 0:
                    # Task complete
                    task.total_latency_ms = (time.time() - task.created_at) * 1000  # Convert to ms
                    task.generated_tokens = task.decode_tokens_remaining
                    completed_tasks.append(task)
                    # Mark sequence as complete (blocks become evictable)
                    self.cache.mark_sequence_complete(task.request_id)
        
        # Remove completed tasks
        for task in completed_tasks:
            self.tasks.remove(task)
        
        return completed_tasks
    
    def get_current_load(self) -> float:
        """Get current load in milliseconds of remaining work."""
        total_load = 0.0
        for task in self.tasks:
            total_load += task.current_latency_ms
        return total_load


async def heartbeat_loop(worker_state: WorkerState):
    """Send periodic heartbeats to router."""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                load = worker_state.get_current_load()
                await session.post(
                    f"{ROUTER_URL}/internal/heartbeat",
                    json={"worker_id": WORKER_ID, "current_load": load},
                )
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(1)


async def sync_loop(worker_state: WorkerState):
    """Sync cache state with router."""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Get all currently cached blocks (not evicted)
                # This includes evictable blocks - they're still cached until actually evicted
                all_cached_blocks = list(worker_state.cache.get_all_block_hashes())
                
                # Try to preserve order using sequences for better prefix matching
                sequences = worker_state.cache.get_all_block_sequences()
                all_blocks = []
                seen = set()
                
                # First, add blocks from sequences in order (for prefix matching)
                if sequences:
                    for seq in sequences:
                        for block_hash in seq:
                            if block_hash in all_cached_blocks and block_hash not in seen:
                                all_blocks.append(block_hash)
                                seen.add(block_hash)
                
                # Add any remaining cached blocks
                for block_hash in all_cached_blocks:
                    if block_hash not in seen:
                        all_blocks.append(block_hash)
                
                # Fallback: if we somehow have no blocks but cache says we do, use all cached
                if not all_blocks:
                    all_blocks = all_cached_blocks
                
                await session.post(
                    f"{ROUTER_URL}/internal/sync",
                    json={"worker_id": WORKER_ID, "active_hashes": all_blocks},
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                if all_blocks:
                    logger.info(f"✅ Synced {len(all_blocks)} blocks to router")
                else:
                    # Debug why no blocks
                    total_cached = len(worker_state.cache.get_all_block_hashes())
                    sequences = worker_state.cache.get_all_block_sequences()
                    logger.warning(
                        f"⚠️  Sync: 0 blocks to send, but cache has {total_cached} blocks, "
                        f"{len(sequences)} sequences"
                    )
            except asyncio.TimeoutError:
                logger.warning("Sync timeout - router may be busy")
            except aiohttp.ClientError as e:
                logger.warning(f"Sync connection error: {e}")
            except Exception as e:
                logger.error(f"Sync error: {e}")
            await asyncio.sleep(5)


async def process_tasks_loop(worker_state: WorkerState):
    """Main task processing loop."""
    while True:
        completed = worker_state.process_tasks(delta_time_ms=1.0)
        for task in completed:
            logger.info(
                f"Task {task.request_id} completed: "
                f"prefill_blocks={len(task.block_hashes) - task.prefill_blocks_to_compute}/{len(task.block_hashes)}, "
                f"decode_tokens={task.decode_tokens_remaining}, "
                f"total_latency={task.total_latency_ms*1000:.2f}ms"
            )
        await asyncio.sleep(0.001)  # Small delay to prevent busy-waiting


async def handle_inference_request(request_data: dict) -> dict:
    """Handle an inference request from the router."""
    prompt = request_data.get("prompt", "")
    max_tokens = request_data.get("max_tokens", 100)
    
    # This would be called by an HTTP endpoint
    # For now, we'll integrate it into the main loop
    pass


async def fake_request_loop(worker_state: WorkerState):
    """Generate fake requests for testing."""
    # Use longer prompts to ensure we get multiple blocks (16 tokens per block)
    prompts = [
        "The quick brown fox jumps over the lazy dog. " * 3,  # Repeat to get more tokens
        "Once upon a time in a galaxy far far away. " * 3,
        "To be or not to be, that is the question. " * 3,
        "In the beginning was the Word, and the Word was with God. " * 2,
    ]
    
    while True:
        await asyncio.sleep(random.uniform(2.0, 5.0))
        prompt = random.choice(prompts)
        task = worker_state.add_task(prompt, max_tokens=random.randint(20, 100))
        logger.info(
            f"Added task {task.request_id}: "
            f"blocks={len(task.block_hashes)}, "
            f"cached={len(task.cached_blocks)}, "
            f"to_compute={task.prefill_blocks_to_compute}, "
            f"prompt_tokens={task.prompt_tokens}"
        )
        # Debug: show current cache state
        total_blocks = len(worker_state.cache.get_all_block_hashes())
        logger.debug(f"Cache now has {total_blocks} blocks total")


async def main():
    logger.info(f"Starting Mock Worker: {WORKER_ID}")
    logger.info(f"Cache capacity: {BLOCKS_PER_GPU} blocks ({BLOCKS_PER_GPU * BLOCK_SIZE} tokens)")
    
    worker_state = WorkerState()
    
    # Start background tasks
    asyncio.create_task(heartbeat_loop(worker_state))
    asyncio.create_task(sync_loop(worker_state))
    asyncio.create_task(process_tasks_loop(worker_state))
    
    # TEMP: fake requests for testing
    asyncio.create_task(fake_request_loop(worker_state))
    
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
