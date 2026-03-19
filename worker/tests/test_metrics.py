from app.metrics import compute_metrics


def test_compute_metrics_empty_detections():
    out = compute_metrics(detections=[], duration_ms=123)
    assert out["tree_count"] == 0
    assert out["avg_confidence"] == 0.0
    assert out["duration_ms"] == 123


def test_compute_metrics_non_empty_detections():
    detections = [
        {"confidence": 0.9},
        {"confidence": 0.6},
        {"confidence": 0.3},
    ]
    out = compute_metrics(detections=detections, duration_ms=77)
    assert out["tree_count"] == 3
    assert out["avg_confidence"] == 0.6
    assert out["duration_ms"] == 77
