# Auto-improvement #335
# Module: prediction_tracking
# Improvement: add_calibration_buckets
# Description: Group predictions by confidence buckets
# Timestamp: 2026-06-08T03:20:46.124745+00:00


def calibration_buckets(predictions, bucket_size=0.1):
    buckets = {}
    for p in predictions:
        bucket = round(p["confidence"] / bucket_size) * bucket_size
        if bucket not in buckets:
            buckets[bucket] = {"total": 0, "correct": 0}
        buckets[bucket]["total"] += 1
        if p["actual_outcome"]:
            buckets[bucket]["correct"] += 1
    return buckets

