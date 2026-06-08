# Auto-improvement #124
# Module: causal_reasoning
# Improvement: add_chain_confidence_decay
# Description: Decay confidence over time for causal chains
# Timestamp: 2026-06-08T03:20:45.993645+00:00


def decay_confidence(chain, days_since_last_evidence):
    base = chain.get("confidence", 0.5)
    decay = 0.95 ** days_since_last_evidence
    return base * decay

