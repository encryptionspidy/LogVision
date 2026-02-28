#!/usr/bin/env python3
"""
Performance benchmark for Log Analyzer.

Measures:
- Ingestion throughput (lines/sec, MB/sec)
- Peak memory usage
- Latency per batch
"""

import time
import os
import sys
import psutil
import tempfile
import random
from datetime import datetime

# Adjust path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.reader import read_lines
from app.ingestion.normalizer import normalize_entries
from app.parsing.parser import parse_log_entries
from app.anomaly.evaluator import evaluate_anomalies
from app.severity.scorer import score_entries
from app.explanation.generator import generate_explanations

def generate_large_log(lines=100_000):
    """Generate a large dummy log file."""
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    
    print(f"Generating {lines} log entries...")
    with open(path, "w") as f:
        for i in range(lines):
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            level = random.choice(["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"])
            msg = f"This is log entry number {i} with some random data {random.randint(0,9999)}"
            f.write(f"{ts} app.service [{os.getpid()}]: {level}: {msg}\n")
    
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"Generated {size_mb:.2f} MB")
    return path

def run_benchmark(file_path):
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss / (1024 * 1024)
    
    start_time = time.time()
    
    # 1. Pipeline
    print("Running pipeline...")
    # Using batches to simulate stream/chunk processing closer to reality, 
    # but here we just run the functions which generator-chain naturally.
    
    count = 0
    raw_lines = read_lines(file_path)
    normalized = normalize_entries(raw_lines)
    entries = parse_log_entries(lines_iter=normalized)
    
    # We must consume the generator to measure time
    # But evaluating anomalies requires list or iterator consumption.
    # evaluate_anomalies expects list.
    
    # For benchmark, lets read all entries first (Parser throughput)
    all_entries = list(entries)
    parse_time = time.time()
    
    if not all_entries:
        print("No entries parsed!")
        return

    # Anomaly
    anomalies = evaluate_anomalies(all_entries)
    
    # Severity
    severities = score_entries(all_entries, anomalies)
    
    # Explanation (only for anomalies/high severity usually, but here we do all to stress test)
    # Actually generator handles all.
    explanations = generate_explanations(all_entries, anomalies, severities)
    
    end_time = time.time()
    
    end_mem = process.memory_info().rss / (1024 * 1024)
    
    total_time = end_time - start_time
    total_lines = len(all_entries)
    
    print("\n--- Results ---")
    print(f"Total Lines:      {total_lines}")
    print(f"Total Time:       {total_time:.4f} s")
    print(f"Throughput:       {total_lines / total_time:.0f} lines/sec")
    print(f"Parse Time:       {parse_time - start_time:.4f} s")
    print(f"Analysis Time:    {end_time - parse_time:.4f} s")
    print(f"Memory Usage:     {end_mem - start_mem:.2f} MB increase (Peak: {end_mem:.2f} MB)")

if __name__ == "__main__":
    path = generate_large_log(lines=50_000)
    try:
        run_benchmark(path)
    finally:
        os.unlink(path)
