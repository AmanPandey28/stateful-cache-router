from transformers import AutoTokenizer
import hashlib
from typing import List, Tuple, Dict

# vLLM block configuration
BLOCK_SIZE = 16  # tokens per block

class TokenizerUtils:
    def __init__(self, model_name: str = "gpt2"):
        # In a real scenario, this would be the actual model path or name
        # Using gpt2 as lightweight tokenizer for consistency
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def tokenize(self, text: str) -> List[int]:
        """Tokenize text and return token IDs."""
        return self.tokenizer.encode(text, add_special_tokens=False)

    def compute_prefix_hash(self, text: str, prefix_len: int = None) -> str:
        """
        Computes a SHA-256 hash of the token IDs for the given text.
        If prefix_len is provided, only hashes the first prefix_len tokens.
        """
        token_ids = self.tokenize(text)
        if prefix_len:
            token_ids = token_ids[:prefix_len]
        
        # Create a stable tuple for hashing
        stable_prefix = tuple(token_ids)
        return hashlib.sha256(str(stable_prefix).encode()).hexdigest()
    
    def compute_block_hashes(self, text: str) -> List[str]:
        """
        Compute hashes for each block of 16 tokens.
        vLLM caches only full blocks, so we hash each block separately.
        Returns list of block hashes.
        """
        token_ids = self.tokenize(text)
        block_hashes = []
        
        # Process in blocks of 16 tokens
        for i in range(0, len(token_ids), BLOCK_SIZE):
            block_tokens = token_ids[i:i + BLOCK_SIZE]
            # Only hash full blocks (vLLM doesn't cache partial blocks)
            if len(block_tokens) == BLOCK_SIZE:
                # Create stable hash for this block
                block_tuple = tuple(block_tokens)
                block_hash = hashlib.sha256(str(block_tuple).encode()).hexdigest()
                block_hashes.append(block_hash)
        
        return block_hashes
    
    def get_num_blocks(self, text: str) -> int:
        """Get the number of full blocks for a given text."""
        token_ids = self.tokenize(text)
        return len(token_ids) // BLOCK_SIZE
    
    def get_num_tokens(self, text: str) -> int:
        """Get the number of tokens for a given text."""
        return len(self.tokenize(text))
