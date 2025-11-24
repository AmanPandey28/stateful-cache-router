"""
vLLM BlockManager Modification Guide

This file demonstrates the modifications needed for vLLM's BlockManager to enable
push-based eviction reporting to the router.

COMPATIBILITY:
- Tested with vLLM v0.2.7 - v0.4.x
- Target file: vllm/core/block_manager_v1.py (or block_manager_v2.py for newer versions)
- Alternative target: vllm/core/block/block_manager.py (v0.5.0+)

INTEGRATION STEPS:

1. Locate the BlockManager class in your vLLM installation:
   - For v0.2.x - v0.4.x: vllm/core/block_manager_v1.py
   - For v0.5.0+: vllm/core/block/block_manager.py
   
2. Find the `free_block()` or `free()` method in the BlockAllocator class

3. Initialize the EvictionReporter in your vLLM engine startup:
   ```python
   from vllm_patch.vllm.engine.eviction_reporter import EvictionReporter
   
   # In LLMEngine.__init__ or similar
   self.eviction_reporter = EvictionReporter(
       router_url=os.getenv("ROUTER_URL", "http://localhost:8000"),
       worker_id=os.getenv("WORKER_ID", "worker-1")
   )
   await self.eviction_reporter.start()
   ```

4. Modify the free_block() method as shown below

5. Verify the patch by checking logs for eviction reports

CRITICAL: Only report evictions when the physical block's reference count drops to 0.
This prevents false eviction reports for blocks still in use by other logical blocks.
"""

from vllm.engine.eviction_reporter import EvictionReporter

# Global or singleton instance of the reporter (needs to be initialized during engine startup)
# eviction_reporter = EvictionReporter(router_url="http://localhost:8000", worker_id="worker-1")

class BlockManagerModification:
    """
    This class shows the method that needs to be modified in the actual BlockManager.
    
    EXACT LOCATION (v0.2.7 - v0.4.x):
    File: vllm/core/block_manager_v1.py
    Class: BlockAllocatorBase or CachedBlockAllocator
    Method: free(block: PhysicalTokenBlock) -> None
    
    EXACT LOCATION (v0.5.0+):
    File: vllm/core/block/block_manager.py
    Class: BlockAllocator
    Method: free(block: Block) -> None
    """
    
    def free_block(self, block):
        """
        Modified version of the free_block method.
        
        Original signature (v0.2.7 - v0.4.x):
            def free(self, block: PhysicalTokenBlock) -> None:
        
        Original signature (v0.5.0+):
            def free(self, block: Block) -> None:
        """
        # --- MODIFICATION START ---
        
        # CRITICAL: Only report eviction when ref_count drops to 0
        # This ensures we don't report blocks still in use by other sequences
        
        if hasattr(block, 'ref_count'):
            block.ref_count -= 1
            
            # Only proceed if this was the last reference
            if block.ref_count == 0:
                # Check if this block was part of a cached prefix
                # vLLM tracks this via block.content_hash or similar metadata
                
                if hasattr(block, 'content_hash') and block.content_hash:
                    # Report eviction to router
                    # Assuming we have access to the global eviction_reporter
                    # self.eviction_reporter.add_evicted_hash(block.content_hash)
                    pass
                
                # Original free logic (return block to free pool)
                # self.free_blocks.append(block)
        
        # --- MODIFICATION END ---
        
        # For reference, the original vLLM logic typically looks like:
        # if block.ref_count == 0:
        #     self.free_blocks.append(block)
        pass

# EXAMPLE INTEGRATION (Pseudo-code):
"""
# In vllm/core/block_manager_v1.py

from vllm_patch.vllm.engine.eviction_reporter import EvictionReporter

class CachedBlockAllocator(BlockAllocatorBase):
    def __init__(self, ..., eviction_reporter: EvictionReporter = None):
        super().__init__(...)
        self.eviction_reporter = eviction_reporter
    
    def free(self, block: PhysicalTokenBlock) -> None:
        block.ref_count -= 1
        
        if block.ref_count == 0:
            # NEW: Report eviction if this was a cached prefix
            if self.eviction_reporter and hasattr(block, 'content_hash'):
                self.eviction_reporter.add_evicted_hash(block.content_hash)
            
            # Original logic
            self.free_blocks.append(block)
"""

