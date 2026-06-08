"""
prediction-tracker.py -- ECOSYSTEM Prediction Tracker

Tracks prediction accuracy using Brier score.
Measures calibration: are 70% predictions correct 70% of the time?

Stores predictions in predictions.jsonl (JSONL, one entry per line).
No external dependencies -- stdlib only.

Usage:
    from prediction_tracker import PredictionTracker
    tracker = PredictionTracker("runtime/agi/predictions.jsonl")
    tracker.record("task will succeed", 0.8, True)
    print(tracker.brier_score())
    print(tracker.calibration())

CLI:
    python prediction-tracker.py stats
    python prediction-tracker.py recent [n]
    python prediction-tracker.py brier [window]
    python prediction-tracker.py calibration [bucket_size]
    python prediction-tracker.py record <prediction> <confidence> <outcome>
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock

# -- Defaults --

DEFAULT_PATH = Path(__file__).parent / "predictions.jsonl"
BRIER_WINDOW = 100
BRIER_INTERVENTION_THRESHOLD = 0.4
MIN_SAMPLES_FOR_INTERVENTION = 10


class PredictionTracker:
    """
    Tracks prediction vs actual outcome, computes calibration metrics.

    Thread-safe for concurrent record() calls.
    Stores entries in predictions.jsonl (JSONL format).
    """

    def __init__(self, tracker_path: str | Path | None = None):
        self._path = Path(tracker_path) if tracker_path else DEFAULT_PATH
        self._entries: list[dict] = []
        self._loaded = False
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # -- Load from disk --

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._entries.append(json.loads(line))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass

    # -- Record --

    def record(self, prediction: str, confidence: float, actual_outcome: bool,
               metadata: dict | None = None) -> dict:
        """Record a prediction and its outcome. Returns the entry dict."""
        entry = {
            "prediction_id": f"pred-{int(time.time()*1000)}-{len(self._entries)}",
            "prediction": prediction,
            "confidence": round(min(max(confidence, 0.0), 1.0), 4),
            "actual_outcome": actual_outcome,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "metadata": metadata or {},
        }
        with self._lock:
            self._entries.append(entry)
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass
        return entry

    # -- Metrics --

    def brier_score(self, window: int = BRIER_WINDOW) -> float:
        """Brier score over last N entries. Lower = better (0 = perfect, 1 = worst)."""
        self._ensure_loaded()
        recent = self._entries[-window:]
        if not recent:
            return 0.0
        score = 0.0
        for e in recent:
            actual = 1.0 if e["actual_outcome"] else 0.0
            score += (e["confidence"] - actual) ** 2
        return round(score / len(recent), 4)

    def accuracy(self, window: int = BRIER_WINDOW) -> float:
        """Directional accuracy: how often the predicted direction matches actual."""
        self._ensure_loaded()
        recent = self._entries[-window:]
        if not recent:
            return 0.0
        correct = sum(
            1 for e in recent
            if (e["confidence"] >= 0.5) == e["actual_outcome"]
        )
        return round(correct / len(recent), 4)

    def calibration(self, bucket_size: float = 0.1) -> dict:
        """
        Calibration data: for each confidence bucket, what was the actual rate?

        Returns dict like:
        {"0.0-0.1": {"avg_predicted": 0.05, "actual_rate": 0.0, "count": 3, "gap": 0.05}, ...}
        """
        self._ensure_loaded()
        if not self._entries:
            return {}

        num_buckets = max(1, int(round(1.0 / bucket_size)))
        buckets: dict = defaultdict(lambda: {"pred_sum": 0.0, "actual_sum": 0.0, "count": 0})

        for e in self._entries:
            idx = min(int(e["confidence"] / bucket_size), num_buckets - 1)
            b = buckets[idx]
            b["pred_sum"] += e["confidence"]
            b["actual_sum"] += 1.0 if e["actual_outcome"] else 0.0
            b["count"] += 1

        result = {}
        for idx in sorted(buckets.keys()):
            b = buckets[idx]
            lo = round(idx * bucket_size, 2)
            hi = round((idx + 1) * bucket_size, 2)
            avg_pred = round(b["pred_sum"] / b["count"], 3) if b["count"] else 0
            actual_rate = round(b["actual_sum"] / b["count"], 3) if b["count"] else 0
            result[f"{lo}-{hi}"] = {
                "avg_predicted": avg_pred,
                "actual_rate": actual_rate,
                "count": b["count"],
                "gap": round(abs(avg_pred - actual_rate), 3),
            }
        return result

    def should_intervene(self) -> bool:
        """Return True if Brier score is too high (worse than coin flip)."""
        self._ensure_loaded()
        if len(self._entries) < MIN_SAMPLES_FOR_INTERVENTION:
            return False
        return self.brier_score() > BRIER_INTERVENTION_THRESHOLD

    def get_stats(self) -> dict:
        """Return full statistics summary."""
        self._ensure_loaded()
        return {
            "total_predictions": len(self._entries),
            "brier_score": self.brier_score(),
            "accuracy": self.accuracy(),
            "should_intervene": self.should_intervene(),
            "calibration": self.calibration(),
        }

    def recent(self, n: int = 10) -> list[dict]:
        """Return last N predictions."""
        self._ensure_loaded()
        return self._entries[-n:]

    def trend(self, window: int = 10) -> dict:
        """
        Analyze prediction trend over recent windows.
        Returns trend direction and magnitude.
        """
        self._ensure_loaded()
        if len(self._entries) < window * 2:
            return {"trend": "insufficient_data", "windows": 0}

        # Split into recent and older windows
        recent = self._entries[-window:]
        older = self._entries[-(window * 2):-window]

        def _accuracy(batch):
            correct = sum(1 for e in batch if e["actual_outcome"])
            return correct / len(batch) if batch else 0

        recent_acc = _accuracy(recent)
        older_acc = _accuracy(older)
        delta = recent_acc - older_acc

        if delta > 0.1:
            trend = "improving"
        elif delta < -0.1:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "recent_accuracy": round(recent_acc, 3),
            "older_accuracy": round(older_acc, 3),
            "delta": round(delta, 3),
            "window": window,
        }


# -- CLI --

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: prediction-tracker.py <stats|recent|brier|calibration|record> [args]")
        sys.exit(1)

    tracker = PredictionTracker()
    cmd = args[0]

    if cmd == "stats":
        stats = tracker.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif cmd == "recent":
        n = int(args[1]) if len(args) > 1 else 10
        entries = tracker.recent(n)
        if not entries:
            print("No predictions recorded yet.")
        else:
            for e in entries:
                mark = "+" if e["actual_outcome"] else "-"
                print(f"  [{mark}] conf={e['confidence']:.2f}  {e['prediction']}  ({e['timestamp']})")
            print(f"\nShowing last {len(entries)} of {tracker.get_stats()['total_predictions']} predictions.")

    elif cmd == "brier":
        window = int(args[1]) if len(args) > 1 else 100
        score = tracker.brier_score(window)
        acc = tracker.accuracy(window)
        total = tracker.get_stats()["total_predictions"]
        print(f"Brier score (last {min(window, total)}): {score}")
        print(f"Directional accuracy: {acc}")
        print(f"Total predictions: {total}")
        if score > BRIER_INTERVENTION_THRESHOLD and total >= MIN_SAMPLES_FOR_INTERVENTION:
            print("WARNING: Brier score exceeds intervention threshold!")

    elif cmd == "calibration":
        bucket_size = float(args[1]) if len(args) > 1 else 0.1
        cal = tracker.calibration(bucket_size)
        if not cal:
            print("No predictions recorded yet.")
        else:
            print(f"{'Bucket':<12} {'Predicted':>10} {'Actual':>10} {'Count':>6} {'Gap':>6}")
            print("-" * 46)
            for bucket, data in cal.items():
                print(f"{bucket:<12} {data['avg_predicted']:>10.3f} {data['actual_rate']:>10.3f} {data['count']:>6} {data['gap']:>6.3f}")

    elif cmd == "record":
        if len(args) < 4:
            print("Usage: prediction-tracker.py record <prediction> <confidence> <true|false> [metadata_json]")
            sys.exit(1)
        prediction = args[1]
        confidence = float(args[2])
        outcome = args[3].lower() in ("true", "1", "yes")
        metadata = json.loads(args[4]) if len(args) > 4 else None
        entry = tracker.record(prediction, confidence, outcome, metadata)
        print(f"Recorded: {entry['prediction_id']} conf={entry['confidence']} outcome={entry['actual_outcome']}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: stats, recent, brier, calibration, record")
        sys.exit(1)


if __name__ == "__main__":
    main()
