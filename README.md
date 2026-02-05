# Stateful Cache-Aware Router for Distributed LLM Inference

Stateful, cache-aware routing for multi-node LLM inference that balances KV-cache locality with load to reduce TTFT and tail latency.

## Why this matters
Stateless routers (round-robin / least-loaded) ignore prefix locality, causing redundant prefill compute under shared-prefix workloads (system prompts, multi-turn chat, RAG).

## What this repo contains
- A vLLM-inspired event-driven latency simulator (paged KV cache + radix trie, continuous batching, chunked prefills, eviction)
- Multiple routing policies:
  - Round Robin
  - Least Loaded
  - Greedy Cache-Aware (max prefix match)
  - Cost-Aware (queue wait vs prefill recomputation)
- A short paper/report with methodology + results

## Key idea (Cost-Aware routing)
Score each worker as:
`T_queue_wait(worker) + T_prefill(prompt_suffix_not_cached)`

Routes to cached worker only when the expected queueing delay is worth the prefill savings.

## Results (high level)
- Greedy cache-maximizing can cause “herding” → hotspots → worse tail latency under bursts
- Cost-aware policy preserves most cache reuse while stabilizing TTFT and end-to-end latency

## Report
See: `report/CACHE-AWARE ROUTING.pdf`


