from transformers import AutoTokenizer
import hashlib
from typing import List, Tuple

class TokenizerUtils:
    def __init__(self, model_name: str = "gpt2"):
        # In a real scenario, this would be the actual model path or name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def tokenize(self, text: str) -> List[int]:
        return self.tokenizer.encode(text)

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
