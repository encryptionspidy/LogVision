#!/usr/bin/env python3
"""
Accuracy evaluation script for the log anomaly detection pipeline.

Expects a labeled CSV with columns: message, is_anomaly, severity
Outputs: Precision, Recall, F1, False Positive Rate, Confusion Matrix.

If no labeled dataset is available, prints:
    UNRESOLVED: No labeled dataset found — cannot compute accuracy metrics.

Usage:
    python scripts/evaluate_accuracy.py [--dataset path/to/labeled.csv]
    python scripts/evaluate_accuracy.py --generate-synthetic  # Create test data
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import LogEntry, LogLevel, SeverityLevel
from app.anomaly.evaluator import evaluate_anomalies
from app.severity.scorer import score_entries


def load_labeled_dataset(path: str) -> list[dict]:
    """Load labeled CSV. Expected columns: message, is_anomaly, severity."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "message": row["message"],
                "is_anomaly": row["is_anomaly"].strip().lower() in ("true", "1", "yes"),
                "severity": row.get("severity", "LOW").strip().upper(),
            })
    return rows


def generate_synthetic_dataset(output_path: str, n: int = 200) -> str:
    """Generate a synthetic labeled dataset for development testing."""
    random.seed(42)

    normal_messages = [
        "User login successful for user_{id}",
        "Request processed in {ms}ms",
        "Health check passed",
        "Cache hit for key session_{id}",
        "Connection established to database",
        "Scheduled task completed: cleanup",
        "File uploaded successfully: report_{id}.pdf",
        "API response sent: 200 OK",
    ]

    anomalous_messages = [
        "FATAL: Out of memory — killing process {pid}",
        "Connection refused to database at 10.0.1.{ip}:5432",
        "Segmentation fault in module auth_handler",
        "Disk usage critical: 98% on /dev/sda1",
        "ERROR: Unhandled exception in payment_service",
        "CRITICAL: SSL certificate expired for api.example.com",
        "Kernel panic — not syncing: VFS: Unable to mount root",
        "ERROR: Database deadlock detected on table orders",
    ]

    rows = []
    for i in range(n):
        if random.random() < 0.25:  # 25% anomaly rate
            msg = random.choice(anomalous_messages).format(
                id=random.randint(100, 999),
                pid=random.randint(1000, 9999),
                ip=random.randint(1, 254),
                ms=random.randint(1, 100),
            )
            severity = random.choice(["HIGH", "CRITICAL"])
            is_anomaly = True
        else:
            msg = random.choice(normal_messages).format(
                id=random.randint(100, 999),
                ms=random.randint(1, 50),
            )
            severity = random.choice(["LOW", "MEDIUM"])
            is_anomaly = False

        rows.append({
            "message": msg,
            "is_anomaly": str(is_anomaly),
            "severity": severity,
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["message", "is_anomaly", "severity"])
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def evaluate(labeled_data: list[dict]) -> dict:
    """
    Run the pipeline on labeled data and compute accuracy metrics.

    Returns dict with precision, recall, f1, fpr, confusion_matrix.
    """
    # Convert to LogEntry
    entries = []
    for i, row in enumerate(labeled_data):
        level = LogLevel.ERROR if row["is_anomaly"] else LogLevel.INFO
        entries.append(LogEntry(
            raw=row["message"],
            line_number=i + 1,
            log_level=level,
            message=row["message"],
            source="eval",
        ))

    # Run pipeline
    anomalies = evaluate_anomalies(entries)
    severities = score_entries(entries, anomalies)

    # Compare predictions vs labels
    tp = fp = tn = fn = 0
    severity_correct = 0

    for i, row in enumerate(labeled_data):
        line_num = i + 1
        predicted_anomaly = anomalies[line_num].is_anomaly
        actual_anomaly = row["is_anomaly"]

        if predicted_anomaly and actual_anomaly:
            tp += 1
        elif predicted_anomaly and not actual_anomaly:
            fp += 1
        elif not predicted_anomaly and actual_anomaly:
            fn += 1
        else:
            tn += 1

        # Severity accuracy
        predicted_severity = severities[line_num].level.value
        if predicted_severity == row["severity"]:
            severity_correct += 1

    total = len(labeled_data)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "total_samples": total,
        "anomaly_detection": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_positive_rate": round(fpr, 4),
            "confusion_matrix": {
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn,
            },
        },
        "severity_classification": {
            "accuracy": round(severity_correct / total, 4) if total > 0 else 0.0,
            "correct": severity_correct,
            "total": total,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate anomaly detection accuracy")
    parser.add_argument("--dataset", type=str, default=None, help="Path to labeled CSV")
    parser.add_argument(
        "--generate-synthetic",
        action="store_true",
        help="Generate synthetic labeled dataset",
    )
    args = parser.parse_args()

    if args.generate_synthetic:
        out = generate_synthetic_dataset("data/synthetic_labeled.csv")
        print(f"Generated synthetic dataset: {out}")
        args.dataset = out

    if args.dataset is None:
        # Try default location
        default_paths = [
            "data/labeled.csv",
            "data/synthetic_labeled.csv",
        ]
        for p in default_paths:
            if os.path.exists(p):
                args.dataset = p
                break

    if args.dataset is None or not os.path.exists(args.dataset):
        print("UNRESOLVED: No labeled dataset found — cannot compute accuracy metrics.")
        print("Run with --generate-synthetic to create a development dataset.")
        sys.exit(1)

    print(f"Loading dataset: {args.dataset}")
    data = load_labeled_dataset(args.dataset)
    print(f"Loaded {len(data)} labeled entries")

    print("\nRunning pipeline...")
    results = evaluate(data)

    print("\n" + "=" * 60)
    print("ACCURACY EVALUATION RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    print("=" * 60)

    # Summary
    ad = results["anomaly_detection"]
    print(f"\nAnomaly Detection:  P={ad['precision']:.2%}  R={ad['recall']:.2%}  F1={ad['f1_score']:.2%}  FPR={ad['false_positive_rate']:.2%}")
    sc = results["severity_classification"]
    print(f"Severity Accuracy:  {sc['accuracy']:.2%}  ({sc['correct']}/{sc['total']})")


if __name__ == "__main__":
    main()
