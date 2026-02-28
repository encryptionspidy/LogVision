"""
Flask API server for the Intelligent Log Analyzer (Phase 4).

Provides:
- POST /analyze       — accept log file upload, return JSON analysis results
- POST /analyze/async — async analysis with job tracking
- GET  /search        — detailed search with filters
- GET  /analytics     — aggregate metrics
- GET  /alerts/config — view current alerting rules
- GET  /timeline      — chronological anomaly timeline
- GET  /root-cause    — grouped root cause events
- GET  /metrics       — system self-observability metrics
- GET  /job/<id>/status — async job status
- POST /token/refresh — refresh JWT token
- GET  /              — serve the web UI
- GET  /health        — health check endpoint

Features:
- Rate limiting
- Background log monitoring, directory watching
- Persistent database connection
- Background worker queue
- System metrics collection
"""

from __future__ import annotations

import os
import time
import tempfile
import logging
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory

from app.config.settings import DEFAULT_CONFIG
from app.ingestion.reader import read_lines, ReaderError
from app.ingestion.normalizer import normalize_entries
from app.parsing.parser import parse_log_entries
from app.anomaly.evaluator import evaluate_anomalies
from app.severity.scorer import score_entries
from app.explanation.generator import generate_explanations
from models.schemas import AnalysisReport, AnomalyResult, SeverityResult, Explanation, AlertConfig

# Phase 2 Imports
from app.storage.database import get_db, init_db
from app.storage.search import search_logs
from app.analytics.metrics import AnalyticsEngine
from app.utils.security import configure_security
from app.monitoring.watcher import LogMonitor
from app.security.auth import (
    require_auth, require_admin, create_token, verify_token,
    ROLE_ADMIN, ROLE_VIEWER,
)
from app.alerts.engine import DEFAULT_RULES

# Phase 4 Imports
from app.root_cause.aggregator import aggregate_root_causes
from app.root_cause.correlation_engine import detect_cascades
from app.timeline.timeline_builder import build_timeline
from app.worker.job_queue import get_job_queue
from app.metrics.system_metrics import get_metrics_collector
from app.security.validators import LoginRequest, TimelineQueryParams, RootCauseQueryParams

logger = logging.getLogger(__name__)

# Resolve UI directory path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_UI_DIR = _PROJECT_ROOT / "ui"

# Global monitor reference to prevent GC
_monitor: LogMonitor | None = None


def create_app(config=None) -> Flask:
    """
    Create and configure the Flask application.
    """
    cfg = config or DEFAULT_CONFIG

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = cfg.api.max_content_length_mb * 1024 * 1024

    # Optimize JSON response
    app.json.sort_keys = False

    # 1. Initialize Persistence
    # Use in-memory DB for tests if not configured, else default file
    db_path = os.getenv("DB_PATH", "logs.db")
    if app.config.get("TESTING"):
        db_path = ":memory:" # or specific test file
    init_db(db_path)

    # 2. Configure Security (Rate Limits, Headers)
    configure_security(app)

    # 2a. Register Dev Auto-Auth Middleware
    from app.security.auth import register_dev_middleware
    register_dev_middleware(app)

    # 2b. Configure CORS
    try:
        from flask_cors import CORS
        CORS(app, resources={
            r"/*": {
                "origins": os.getenv("CORS_ORIGINS", "*").split(","),
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        })
    except ImportError:
        logger.warning("flask-cors not installed — CORS not configured")

    # 3. Start Monitoring (if enabled)
    # We use a simple global check to avoid starting multiple monitors on reloads
    global _monitor
    if cfg.monitor.enabled and cfg.monitor.log_path and not _monitor:
        if os.path.exists(cfg.monitor.log_path):
            _monitor = LogMonitor(cfg.monitor.log_path)
            _monitor.start()
        else:
            logger.warning("Monitor path %s does not exist", cfg.monitor.log_path)

    # ── Allowed extensions ──────────────────────────────────────────

    allowed_extensions = {ext.lstrip(".") for ext in cfg.ingestion.allowed_extensions}

    def _allowed_file(filename: str) -> bool:
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in allowed_extensions
        )

    # ── Routes ──────────────────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def serve_ui():
        """Serve the web UI."""
        return send_from_directory(str(_UI_DIR), "index.html")

    @app.route("/ui/<path:filename>", methods=["GET"])
    def serve_ui_assets(filename):
        """Serve UI static assets."""
        return send_from_directory(str(_UI_DIR), filename)

    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        status = {
            "status": "healthy",
            "version": "2.0.0",
            "monitoring": "active" if _monitor else "disabled",
            "database": "connected"
        }
        return jsonify(status), 200

    @app.route("/search", methods=["GET"])
    def search_endpoint():
        """
        Search persistent logs.
        params: q, severity, start, end, limit, offset
        """
        query = request.args.get("q")
        severity = request.args.get("severity")
        start_str = request.args.get("start")
        end_str = request.args.get("end")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        # Parse dates
        start_date = None
        end_date = None
        try:
            if start_str: start_date = datetime.fromisoformat(start_str)
            if end_str: end_date = datetime.fromisoformat(end_str)
        except ValueError:
            return jsonify({"error": "Invalid date format. Use ISO 8601"}), 400

        try:
            results = search_logs(
                query=query,
                severity=severity,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
            return jsonify(results), 200
        except Exception as e:
            logger.exception("Search failed")
            return jsonify({"error": "Search failed", "detail": str(e)}), 500

    @app.route("/analytics", methods=["GET"])
    def analytics_endpoint():
        """Get integrated dashboard metrics."""
        hours = request.args.get("hours", 24, type=int)
        try:
            engine = AnalyticsEngine()
            metrics = engine.get_summary_metrics(hours=hours)
            return jsonify(metrics), 200
        except Exception as e:
            logger.exception("Analytics failed")
            return jsonify({"error": "Analytics calculation failed", "detail": str(e)}), 500

    @app.route("/alerts/config", methods=["GET"])
    def alerts_config():
        """Get current alert rules."""
        from dataclasses import asdict
        return jsonify([asdict(r) for r in DEFAULT_RULES]), 200

    @app.route("/login", methods=["POST"])
    def login():
        """Generate a JWT token. Dev-mode: accepts any username."""
        data = request.get_json(silent=True) or {}
        try:
            validated = LoginRequest(**data)
        except Exception as e:
            return jsonify({"error": f"Validation error: {e}"}), 400
        username = validated.username
        role = data.get("role", ROLE_VIEWER)
        token = create_token(username, role)
        return jsonify({"token": token, "username": username, "role": role}), 200

    @app.route("/analyze", methods=["POST"])
    @require_admin
    def analyze():
        """
        Analyze an uploaded log file (Batch Mode).
        Persists results to DB as well.
        """
        # Validate file presence
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename is None or file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not _allowed_file(file.filename):
            return jsonify({"error": "Unsupported file type"}), 400

        # Save to temp file for processing
        tmp_fd = None
        tmp_path = None
        try:
            suffix = Path(file.filename).suffix
            # Use lower level mkstemp to avoid permission issues sometimes seen with TemporaryFile sharing
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            
            # Write bytes to the file descriptor
            # We can't just use file.save(tmp_path) directly sometimes if the FD is open locked on Windows,
            # but usually fine on Linux. Standard usage:
            os.close(tmp_fd) # Close handle so we can reopen as needed or let Flask handle it
            tmp_fd = None
            
            file.save(tmp_path)

            # Run analysis pipeline
            results = _run_pipeline(tmp_path)
            
            # Persist batch results (Phase 2 requirement)
            # This allows search/analytics to include manual uploads too
            try:
                db = get_db()
                db.insert_reports(results)
            except Exception as e:
                logger.error("Failed to persist batch results: %s", e)
                # Don't fail the request, just log it

            return jsonify({
                "filename": file.filename,
                "total_entries": len(results),
                "results": [r.to_dict() for r in results],
                "summary": _generate_summary(results),
            }), 200

        except ReaderError as e:
            logger.warning("Reader error: %s", e)
            return jsonify({"error": "File processing error", "detail": str(e)}), 422
        except Exception as e:
            logger.exception("Unexpected error during analysis")
            return jsonify({"error": "Internal server error"}), 500
        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            # Just in case cleanup
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass

    # ── Phase 4 Routes ──────────────────────────────────────────────

    @app.route("/timeline", methods=["GET"])
    def timeline_endpoint():
        """Get chronological anomaly timeline."""
        try:
            params = TimelineQueryParams(
                hours=request.args.get("hours", 6, type=int),
                bucket=request.args.get("bucket", 15, type=int),
            )
        except Exception as e:
            return jsonify({"error": f"Validation error: {e}"}), 400
        try:
            db = get_db()
            reports = db.get_recent_reports(hours=params.hours)
            timeline = build_timeline(reports, hours=params.hours, bucket_minutes=params.bucket)
            return jsonify([e.to_dict() for e in timeline]), 200
        except Exception as e:
            logger.exception("Timeline generation failed")
            return jsonify({"error": "Timeline generation failed", "detail": str(e)}), 500

    @app.route("/root-cause", methods=["GET"])
    def root_cause_endpoint():
        """Get grouped root cause events."""
        try:
            params = RootCauseQueryParams(
                hours=request.args.get("hours", 24, type=int),
                min_group=request.args.get("min_group", 2, type=int),
            )
        except Exception as e:
            return jsonify({"error": f"Validation error: {e}"}), 400
        try:
            db = get_db()
            reports = db.get_recent_reports(hours=params.hours)
            anomalous = [r for r in reports if r.anomaly.is_anomaly]
            root_causes = aggregate_root_causes(anomalous, min_group_size=params.min_group)
            root_causes = detect_cascades(root_causes)
            return jsonify([e.to_dict() for e in root_causes]), 200
        except Exception as e:
            logger.exception("Root cause analysis failed")
            return jsonify({"error": "Root cause analysis failed", "detail": str(e)}), 500

    @app.route("/metrics", methods=["GET"])
    def metrics_endpoint():
        """Get system self-observability metrics."""
        try:
            collector = get_metrics_collector()
            queue = get_job_queue()
            collector.record_queue_size(queue.get_queue_size())
            metrics = collector.get_metrics()
            return jsonify(metrics.to_dict()), 200
        except Exception as e:
            logger.exception("Metrics collection failed")
            return jsonify({"error": "Metrics collection failed"}), 500

    @app.route("/analyze/async", methods=["POST"])
    @require_admin
    def analyze_async():
        """Submit a log file for async analysis. Returns job_id immediately."""
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename is None or file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not _allowed_file(file.filename):
            return jsonify({"error": "Unsupported file type"}), 400

        try:
            suffix = Path(file.filename).suffix
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.close(tmp_fd)
            file.save(tmp_path)

            queue = get_job_queue()
            job_id = queue.submit_job(_run_pipeline_and_persist, tmp_path)

            return jsonify({"job_id": job_id, "status": "PENDING"}), 202

        except Exception as e:
            logger.exception("Async analysis submission failed")
            return jsonify({"error": "Submission failed"}), 500

    @app.route("/job/<job_id>/status", methods=["GET"])
    def job_status_endpoint(job_id):
        """Get the status of an async analysis job."""
        queue = get_job_queue()
        status = queue.get_status(job_id)
        if status is None:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(status.to_dict()), 200

    @app.route("/token/refresh", methods=["POST"])
    @require_auth
    def refresh_token():
        """Refresh a valid JWT token."""
        import jwt as pyjwt
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing token"}), 401
        token = auth_header[7:]
        try:
            payload = verify_token(token)
            new_token = create_token(payload["sub"], payload.get("role", ROLE_VIEWER))
            return jsonify({"token": new_token}), 200
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

    return app


def _run_pipeline_and_persist(file_path: str) -> list[AnalysisReport]:
    """Run analysis pipeline and persist results. Used by async workers."""
    try:
        results = _run_pipeline(file_path)
        try:
            db = get_db()
            db.insert_reports(results)
        except Exception as e:
            logger.error("Failed to persist async results: %s", e)
        return results
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass


def _run_pipeline(file_path: str) -> list[AnalysisReport]:
    """Run the complete analysis pipeline on a file."""
    start_time = time.monotonic()
    collector = get_metrics_collector()
    success = True

    try:
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

    except Exception:
        success = False
        raise
    finally:
        duration_ms = (time.monotonic() - start_time) * 1000
        collector.record_request(duration_ms, success)


def _generate_summary(reports: list[AnalysisReport]) -> dict:
    """Generate a summary of analysis results."""
    total = len(reports)
    anomaly_count = sum(1 for r in reports if r.anomaly.is_anomaly)

    severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for r in reports:
        severity_counts[r.severity.level.value] += 1

    return {
        "total_entries": total,
        "anomalies_detected": anomaly_count,
        "anomaly_percentage": round(anomaly_count / total * 100, 1) if total else 0,
        "severity_distribution": severity_counts,
    }
