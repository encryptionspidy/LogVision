#!/usr/bin/env python3
"""
Intelligent Log & Error Analyzer — Main entry point.

Provides both CLI analysis and API server modes.

Usage:
    python main.py analyze <file>        Analyze a log file (CLI output)
    python main.py analyze <file> --json Output as JSON
    python main.py serve                 Start the web API server
    python main.py serve --port 8080     Start on custom port
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import DEFAULT_CONFIG
from app.ingestion.reader import read_lines, ReaderError
from app.ingestion.normalizer import normalize_entries
from app.parsing.parser import parse_log_entries
from app.anomaly.evaluator import evaluate_anomalies
from app.severity.scorer import score_entries
from app.explanation.generator import generate_explanations
from models.schemas import AnalysisReport, AnomalyResult, SeverityResult, Explanation


# ── ANSI Colors for CLI ─────────────────────────────────────────────

_COLORS = {
    "CRITICAL": "\033[91m",  # Red
    "HIGH": "\033[93m",      # Yellow/Orange
    "MEDIUM": "\033[33m",    # Yellow
    "LOW": "\033[92m",       # Green
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
}


def _colorize(text: str, severity: str) -> str:
    """Wrap text in ANSI color based on severity."""
    color = _COLORS.get(severity, "")
    return f"{color}{text}{_COLORS['RESET']}"


# ── Pipeline ────────────────────────────────────────────────────────

def run_analysis(file_path: str) -> list[AnalysisReport]:
    """
    Run the complete analysis pipeline on a log file.

    Args:
        file_path: Path to the log file.

    Returns:
        List of AnalysisReport objects.

    Raises:
        ReaderError: If file validation fails.
    """
    # 1. Ingest
    raw_lines = read_lines(file_path)

    # 2. Normalize
    normalized = normalize_entries(raw_lines)

    # 3. Parse
    entries = parse_log_entries(lines_iter=normalized)

    if not entries:
        return []

    # 4. Anomaly Detection
    anomalies = evaluate_anomalies(entries)

    # 5. Severity Scoring
    severities = score_entries(entries, anomalies)

    # 6. Explanation Generation
    explanations = generate_explanations(entries, anomalies, severities)

    # 7. Assemble Reports
    reports: list[AnalysisReport] = []
    for entry in entries:
        report = AnalysisReport(
            log_entry=entry,
            anomaly=anomalies.get(entry.line_number, AnomalyResult()),
            severity=severities.get(entry.line_number, SeverityResult()),
            explanation=explanations.get(entry.line_number, Explanation()),
        )
        reports.append(report)

    return reports


# ── CLI Output ──────────────────────────────────────────────────────

def print_cli_results(reports: list[AnalysisReport]) -> None:
    """Print analysis results in formatted CLI output."""
    if not reports:
        print("No log entries found in the file.")
        return

    # Summary
    total = len(reports)
    anomaly_count = sum(1 for r in reports if r.anomaly.is_anomaly)
    severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for r in reports:
        severity_counts[r.severity.level.value] += 1

    print(f"\n{_COLORS['BOLD']}═══ Log Analysis Report ═══{_COLORS['RESET']}")
    print(f"Total entries: {total}")
    print(f"Anomalies:     {anomaly_count} ({anomaly_count/total*100:.1f}%)")
    crit_count = severity_counts["CRITICAL"]
    high_count = severity_counts["HIGH"]
    med_count = severity_counts["MEDIUM"]
    low_count = severity_counts["LOW"]
    print(f"Severity:      "
          f"{_colorize(f'CRITICAL:{crit_count}', 'CRITICAL')}  "
          f"{_colorize(f'HIGH:{high_count}', 'HIGH')}  "
          f"{_colorize(f'MEDIUM:{med_count}', 'MEDIUM')}  "
          f"{_colorize(f'LOW:{low_count}', 'LOW')}")
    print()

    # Show anomalous entries (sorted by severity)
    anomalous = [r for r in reports if r.anomaly.is_anomaly]
    if not anomalous:
        print("No anomalies detected. All entries appear normal.")
        return

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    anomalous.sort(key=lambda r: order.get(r.severity.level.value, 4))

    print(f"{_COLORS['BOLD']}── Anomalous Entries ──{_COLORS['RESET']}\n")
    for r in anomalous:
        sev = r.severity.level.value
        line = r.log_entry.line_number
        msg = r.log_entry.message[:120]
        score = r.severity.score

        print(f"  {_colorize(f'[{sev}]', sev)}  "
              f"{_COLORS['DIM']}L{line}{_COLORS['RESET']}  "
              f"score={score:.3f}  {msg}")

        if r.explanation.summary:
            print(f"    ↳ {r.explanation.summary}")

        if r.explanation.possible_causes:
            for cause in r.explanation.possible_causes[:2]:
                print(f"      • {cause}")

        print()


def print_json_results(reports: list[AnalysisReport]) -> None:
    """Print analysis results as JSON."""
    output = {
        "total_entries": len(reports),
        "results": [r.to_dict() for r in reports],
    }
    print(json.dumps(output, indent=2))


# ── CLI Commands ────────────────────────────────────────────────────

def cmd_analyze(args: argparse.Namespace) -> int:
    """Handle the 'analyze' command."""
    try:
        reports = run_analysis(args.file)
    except ReaderError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        logging.exception("Analysis failed")
        return 1

    if args.json:
        print_json_results(reports)
    else:
        print_cli_results(reports)

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Handle the 'serve' command."""
    from api.server import create_app

    config = DEFAULT_CONFIG
    app = create_app(config)

    host = args.host or config.api.host
    port = args.port or config.api.port
    debug = args.debug

    print(f"\n⚡ Log Analyzer API starting on http://{host}:{port}")
    print(f"   Web UI: http://localhost:{port}")
    print(f"   Health: http://localhost:{port}/health\n")

    app.run(host=host, port=port, debug=debug)
    return 0


# ── Argument Parser ─────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="log-analyzer",
        description="Intelligent Log & Error Analyzer",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a log file")
    analyze_parser.add_argument("file", help="Path to the log file")
    analyze_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the web API server")
    serve_parser.add_argument("--host", default=None, help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=None, help="Port to listen on")
    serve_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    serve_parser.set_defaults(func=cmd_serve)

    return parser


def main() -> int:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
