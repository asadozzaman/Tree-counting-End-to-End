from __future__ import annotations


def compute_metrics(detections: list[dict], duration_ms: int) -> dict:
    tree_count = len(detections)
    avg_confidence = 0.0
    if tree_count:
        avg_confidence = round(sum(float(d["confidence"]) for d in detections) / tree_count, 6)

    return {
        "tree_count": int(tree_count),
        "avg_confidence": float(avg_confidence),
        "duration_ms": int(duration_ms),
    }
