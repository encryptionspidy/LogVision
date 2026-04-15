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

from dotenv import load_dotenv
load_dotenv()

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
from app.explanation.deep_explainer import upgrade_explanations
from models.schemas import AnalysisReport, AnomalyResult, SeverityResult, Explanation, AlertConfig

# Phase 2 Imports
from app.storage.database import get_db, init_db
from app.storage.search import search_logs
from app.analytics.metrics import AnalyticsEngine
from app.analytics.insight_engine import InsightEngine
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
from app.analysis.root_cause_engine import build_root_causes
from app.analysis.pattern_analyzer import detect_patterns
from app.analysis.relationship_mapper import map_relationships
from app.analysis.incident_builder import build_incidents, build_system_story
from app.timeline.timeline_builder import build_timeline
from app.analysis.summary_builder import build_summary_report
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
                "origins": "*",
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
        """Serve the enhanced web UI."""
        enhanced_ui_path = _UI_DIR / "enhanced_index.html"
        if enhanced_ui_path.exists():
            return send_from_directory(str(_UI_DIR), "enhanced_index.html")
        return send_from_directory(str(_UI_DIR), "index.html")

    @app.route("/ui/<path:filename>", methods=["GET"])
    def serve_ui_assets(filename):
        """Serve UI static assets."""
        return send_from_directory(str(_UI_DIR), filename)

    # =====================
    # CHAT-DRIVEN ANALYSIS ENDPOINTS (DB-PERSISTED)
    # =====================
    
    @app.route("/analysis/start", methods=["POST"])
    @app.route("/api/analysis/start", methods=["POST"])
    def start_analysis():
        """Start new chat-driven log analysis."""
        from app.llm.router import get_llm_router
        from app.storage.temp_log_store import get_temp_log_store
        import uuid
        import json as _json
        
        log_text = ""
        instruction = ""
        question = ""
        features = []
        log_size_bytes = 0

        if request.is_json:
            data = request.get_json()
            log_text = data.get("log_text", "")
            instruction = data.get("instruction", "")
            question = data.get("question", "")
            features = data.get("features", [])
            log_size_bytes = len(log_text.encode('utf-8')) if log_text else 0
        else:
            instruction = request.form.get("instruction", "")
            question = request.form.get("question", "")
            if "file" in request.files:
                file = request.files["file"]
                # Check file size before reading
                file.seek(0, os.SEEK_END)
                log_size_bytes = file.tell()
                file.seek(0)
                
                # Validate against config limit
                if log_size_bytes > cfg.ingestion.max_file_size_bytes:
                    return jsonify({
                        "error": f"File too large",
                        "detail": f"File size ({log_size_bytes / 1024 / 1024:.1f}MB) exceeds maximum ({cfg.ingestion.max_file_size_bytes / 1024 / 1024:.1f}MB)"
                    }), 413
                
                # Stream read the file in chunks
                chunks = []
                chunk_size = cfg.ingestion.read_buffer_size
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk.decode('utf-8', errors='replace'))
                log_text = ''.join(chunks)
            else:
                log_text = request.form.get("log_text", "")
                log_size_bytes = len(log_text.encode('utf-8')) if log_text else 0
        
        if not log_text:
            return jsonify({"error": "log_text or file required"}), 400
        
        analysis_id = str(uuid.uuid4())
        
        # Store logs temporarily for context reuse
        temp_store = get_temp_log_store()
        try:
            temp_entry = temp_store.store(analysis_id, log_text, filename="logs.txt")
            logger.info(f"Stored temporary logs for session {analysis_id}: size={log_size_bytes}")
        except Exception as e:
            logger.warning(f"Failed to store temporary logs: {e}")
            # Continue without temporary storage (non-critical)
        
        # Build structured context pipeline
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".log")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(log_text)
            
            reports = _run_pipeline(tmp_path)
            stats = _generate_summary(reports)
            
            anomalies = []
            for r in reports:
                if r.anomaly.is_anomaly:
                    anomalies.append({
                        "pattern": r.anomaly.anomaly_type,
                        "severity": r.severity.level.value,
                        "example_log": r.log_entry.raw[:200]
                    })
                    
            payload_context = {
                "raw_logs": log_text,
                "features": features,
                "stats": stats,
                "anomalies": anomalies,
                "severity_distribution": stats.get("severity_distribution", {})
            }
        except Exception as e:
            logger.exception("Pipeline failed, falling back to raw logs: %s", str(e))
            payload_context = {
                "raw_logs": log_text,
                "features": features,
                "stats": {},
                "anomalies": [],
                "severity_distribution": {}
            }
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        
        # Use question as instruction if instruction is empty
        effective_instruction = instruction or question
        
        try:
            llm = get_llm_router()
            result = llm.generate_analysis(payload_context, effective_instruction)
            structured_data = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
            
            # Extract adaptive narrative markdown
            chat_md = (
                structured_data.get("narrative_markdown", "")
                or structured_data.get("chat_response", "")
                or structured_data.get("summary", "Analysis complete")
            )
            
            # Extract SRE-grade intelligence fields
            key_insight = structured_data.get("key_insight", "")
            core_problem = structured_data.get("core_problem", {})
            causal_chain = structured_data.get("causal_chain", [])
            impact_assessment = structured_data.get("impact_assessment", {})
            root_cause_hypothesis = structured_data.get("root_cause_hypothesis", {})
            recommended_actions = structured_data.get("recommended_actions", [])
            confidence_explanation = structured_data.get("confidence_explanation", "")
            
            # Extract enhanced metadata for dynamic insights panel
            risk_level = "UNKNOWN"
            insights = structured_data.get("insights", [])
            fixes = structured_data.get("fixes", {})
            security = structured_data.get("security_analysis", {})
            evidence = structured_data.get("evidence", [])
            quality_metrics = structured_data.get("quality_metrics", {})
            
            # Determine risk level from multiple sources
            if core_problem.get("severity"):
                risk_level = core_problem["severity"]
            elif security.get("threat_level"):
                risk_level = security["threat_level"]
            elif insights:
                high_severity = any(insight.get("severity") == "HIGH" for insight in insights)
                critical_severity = any(insight.get("severity") == "CRITICAL" for insight in insights)
                if critical_severity:
                    risk_level = "CRITICAL"
                elif high_severity:
                    risk_level = "HIGH"
                else:
                    risk_level = "MEDIUM"
            
            # Build enhanced metadata for frontend with SRE intelligence
            session_meta = {
                "status": "complete",
                # SRE intelligence fields
                "key_insight": key_insight,
                "core_problem": core_problem,
                "causal_chain": causal_chain,
                "impact_assessment": impact_assessment,
                "root_cause_hypothesis": root_cause_hypothesis,
                "recommended_actions": recommended_actions,
                "confidence_explanation": confidence_explanation,
                # Existing fields
                "metrics": structured_data.get("metrics", {}),
                "insights": insights,
                "root_causes": structured_data.get("root_causes", []),
                "evidence": evidence,
                "fixes": fixes,
                "security_analysis": security,
                "patterns": structured_data.get("patterns", []),
                "confidence": structured_data.get("confidence", ""),
                "quality_metrics": quality_metrics,
                "actionable_commands": len(fixes.get("commands", [])),
                "evidence_count": len(evidence),
                "insight_count": len(insights),
                "has_security_issues": bool(security.get("indicators")),
                "user_intent": payload_context.get("user_intent", "general"),
                # Log storage metadata for context reuse
                "log_storage": {
                    "size_bytes": log_size_bytes,
                    "has_temp_storage": temp_entry is not None if 'temp_entry' in locals() else False
                },
                # Add chart-ready data
                "charts": {
                    "severity_distribution": structured_data.get("metrics", {}).get("severity_distribution", []),
                    "timeline": structured_data.get("metrics", {}).get("timeline_data", []),
                    "top_patterns": structured_data.get("metrics", {}).get("pattern_counts", []),
                    "affected_components": structured_data.get("metrics", {}).get("affected_components", []),
                }
            }
            
            # Persist to database
            db = get_db()
            db.save_session(
                session_id=analysis_id,
                summary=key_insight or chat_md[:200],  # Use key_insight for sidebar if available
                risk_level=risk_level,
                metadata_json=_json.dumps(session_meta, default=str),
            )
            # Persist user's initial question before the assistant response
            if question:
                db.save_message(analysis_id, "user", question)
            db.save_message(analysis_id, "assistant", chat_md)
            
            return jsonify({
                "analysis_id": analysis_id,
                "status": "started",
                "risk_level": risk_level,
                "key_insight": key_insight,
                "actionable_items": len(recommended_actions) or len(fixes.get("commands", [])),
                "evidence_count": len(evidence),
                "confidence": root_cause_hypothesis.get("confidence", 50)
            })
        except Exception as e:
            logger.exception("LLM processing failed: %s", str(e))
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/analysis/history", methods=["GET"])
    @app.route("/api/analysis/sessions", methods=["GET"])
    def get_analysis_history():
        """Get all analysis sessions for sidebar."""
        db = get_db()
        limit = request.args.get("limit", 50, type=int)
        sessions = db.get_sessions(limit=limit)
        return jsonify(sessions)

    @app.route("/analysis/<analysis_id>", methods=["GET"])
    @app.route("/api/analysis/<analysis_id>", methods=["GET"])
    def get_analysis(analysis_id):
        """Get analysis results with chat history and infographic data."""
        db = get_db()
        session = db.get_session(analysis_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        messages = db.get_messages(analysis_id)
        
        # Extract metadata for infographic data
        # Note: metadata is already spread into session dict by get_session()
        
        # Build response with SRE intelligence data
        response = {
            "id": session["id"],
            "summary": session["summary"],
            "risk_level": session["risk_level"],
            "created_at": session.get("created_at"),
            "messages": messages,
            # SRE intelligence fields
            "key_insight": session.get("key_insight", ""),
            "core_problem": session.get("core_problem", {}),
            "causal_chain": session.get("causal_chain", []),
            "impact_assessment": session.get("impact_assessment", {}),
            "root_cause_hypothesis": session.get("root_cause_hypothesis", {}),
            "recommended_actions": session.get("recommended_actions", []),
            "confidence_explanation": session.get("confidence_explanation", ""),
            # Visualization data
            "metrics": session.get("metrics", {}),
            "charts": {
                "severity_distribution": session.get("metrics", {}).get("severity_distribution", []),
                "timeline": session.get("metrics", {}).get("timeline_data", []),
                "top_patterns": session.get("metrics", {}).get("pattern_counts", []),
                "affected_components": session.get("metrics", {}).get("affected_components", []),
            },
            "insights": session.get("insights", []),
            "anomalies": session.get("patterns", []),
            "confidence": session.get("confidence", 0),
        }
        
        # Add anomaly_score if available
        if session.get("metrics", {}).get("anomaly_score"):
            response["metrics"]["anomaly_score"] = session["metrics"]["anomaly_score"]
        
        return jsonify(response)
    
    @app.route("/analysis/<analysis_id>/chat", methods=["POST"])
    @app.route("/api/analysis/<analysis_id>/chat", methods=["POST"])
    def chat_analysis(analysis_id):
        """Follow-up question on analysis."""
        from app.llm.router import get_llm_router
        
        data = request.get_json()
        question = data.get("question", "")
        
        if not question:
            return jsonify({"error": "question required"}), 400
        
        # Load session context from DB
        db = get_db()
        session = db.get_session(analysis_id)
        context = {}
        if session:
            context = {
                "structured_state": {
                    "key_insight": session.get("key_insight", ""),
                    "core_problem": session.get("core_problem", {}),
                    "causal_chain": session.get("causal_chain", []),
                    "impact_assessment": session.get("impact_assessment", {}),
                    "root_cause_hypothesis": session.get("root_cause_hypothesis", {}),
                    "recommended_actions": session.get("recommended_actions", []),
                    "insights": session.get("insights", []),
                    "metrics": session.get("metrics", {}),
                },
                "log_snippet": ""
            }
        
        # Load chat history for context
        messages = db.get_messages(analysis_id)
        history = [{"role": m["role"], "content": m["content"]} for m in messages[-6:]]
        
        try:
            llm = get_llm_router()
            answer = llm.answer_question(question, context, history=history)
            answer_text = answer.get("answer", "") if isinstance(answer, dict) else str(answer)
            
            # Persist both messages
            db.save_message(analysis_id, "user", question)
            db.save_message(analysis_id, "assistant", answer_text)
            
            return jsonify({
                "question": question,
                "answer": answer_text
            })
        except Exception as e:
            logger.exception("LLM processing failed: %s", str(e))
            return jsonify({"error": str(e)}), 500

    # =====================
    # EXISTING ENDPOINTS
    # =====================

    @app.route("/api/analysis/<session_id>", methods=["GET"])
    def get_analysis_session(session_id):
        """Get a specific analysis session with all details."""
        try:
            db = get_db()
            session = db.get_session(session_id)
            
            if not session:
                return jsonify({"error": "Session not found"}), 404
            
            # Get messages for this session
            messages = db.get_messages(session_id)
            
            return jsonify({
                "id": session["id"],
                "summary": session["summary"],
                "risk_level": session["risk_level"],
                "created_at": session["created_at"],
                "metadata": json.loads(session["metadata_json"]) if session.get("metadata_json") else {},
                "messages": messages
            })
        except Exception as e:
            logger.exception("Failed to get session: %s", str(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/api/analysis/<session_id>", methods=["PATCH"])
    def update_analysis_session(session_id):
        """Update a session (e.g., rename)."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            db = get_db()
            
            # Update session summary if provided
            if "summary" in data:
                db.update_session_summary(session_id, data["summary"])
            
            return jsonify({"status": "updated"})
        except Exception as e:
            logger.exception("Failed to update session: %s", str(e))
            return jsonify({"error": str(e)}), 500

    @app.route("/api/analysis/<session_id>", methods=["DELETE"])
    def delete_analysis_session(session_id):
        """Delete a session and all its messages."""
        try:
            db = get_db()
            
            # Delete session (cascade deletes messages)
            db.delete_session(session_id)
            
            return jsonify({"status": "deleted"})
        except Exception as e:
            logger.exception("Failed to delete session: %s", str(e))
            return jsonify({"error": str(e)}), 500

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

    # ── Phase 5 Analysis Routes ─────────────────────────────────────────
    @app.route("/analysis/summary", methods=["GET"])
    def analysis_summary_endpoint():
        """Get executive narrative + chart-ready payloads."""
        hours = request.args.get("hours", 24, type=int)
        max_anomalies = request.args.get("max_anomalies", 5000, type=int)
        time_window_seconds = request.args.get("time_window_seconds", 300, type=int)
        min_group = request.args.get("min_group", 2, type=int)

        try:
            db = get_db()
            reports = db.get_recent_reports(hours=hours)
            severity_distribution: dict[str, int] = {}
            for r in reports:
                key = r.severity.level.value
                severity_distribution[key] = severity_distribution.get(key, 0) + 1

            anomaly_reports = [r for r in reports if r.anomaly.is_anomaly]
            if max_anomalies and len(anomaly_reports) > max_anomalies:
                anomaly_reports = sorted(anomaly_reports, key=lambda x: x.anomaly.confidence, reverse=True)[:max_anomalies]

            root_causes = build_root_causes(
                anomaly_reports,
                time_window_seconds=time_window_seconds,
                min_group_size=min_group,
            )
            patterns = detect_patterns(anomaly_reports)

            insight_engine = InsightEngine()
            insight_payload = insight_engine.get_overview_charts(hours=hours)
            charts = insight_payload.get("charts", {})

            summary = build_summary_report(
                period_hours=hours,
                total_entries=len(reports),
                anomaly_count=len([r for r in reports if r.anomaly.is_anomaly]),
                severity_distribution=severity_distribution,
                root_causes=root_causes,
                patterns=patterns,
                cluster_distribution=charts.get("cluster_distribution"),
                charts=charts,
            )

            relationships = map_relationships(anomaly_reports)
            incidents = build_incidents(
                reports=anomaly_reports,
                root_causes=root_causes,
                patterns=patterns,
                relationships=relationships,
            )
            summary["incidents"] = [i.to_dict() for i in incidents]
            summary["system_story"] = build_system_story(
                incidents=incidents,
                patterns=patterns,
                period_hours=hours,
            )

            return jsonify(summary), 200
        except Exception as e:
            logger.exception("Analysis summary failed")
            return jsonify({"error": "Analysis summary failed", "detail": str(e)}), 500

    @app.route("/analysis/incidents", methods=["GET"])
    def analysis_incidents_endpoint():
        """Build incident list from clustered anomalies and relationships."""
        hours = request.args.get("hours", 24, type=int)
        max_anomalies = request.args.get("max_anomalies", 5000, type=int)
        time_window_seconds = request.args.get("time_window_seconds", 300, type=int)
        min_group = request.args.get("min_group", 2, type=int)

        try:
            db = get_db()
            reports = db.get_recent_reports(hours=hours)
            anomaly_reports = [r for r in reports if r.anomaly.is_anomaly]

            if max_anomalies and len(anomaly_reports) > max_anomalies:
                anomaly_reports = sorted(anomaly_reports, key=lambda x: x.anomaly.confidence, reverse=True)[:max_anomalies]

            root_causes = build_root_causes(
                anomaly_reports,
                time_window_seconds=time_window_seconds,
                min_group_size=min_group,
            )
            patterns = detect_patterns(anomaly_reports)
            relationships = map_relationships(anomaly_reports)
            incidents = build_incidents(
                reports=anomaly_reports,
                root_causes=root_causes,
                patterns=patterns,
                relationships=relationships,
            )

            return jsonify([i.to_dict() for i in incidents]), 200
        except Exception as e:
            logger.exception("Analysis incidents failed")
            return jsonify({"error": "Analysis incidents failed", "detail": str(e)}), 500

    @app.route("/analysis/story", methods=["GET"])
    def analysis_story_endpoint():
        """Return a single narrative system story for the selected period."""
        hours = request.args.get("hours", 24, type=int)
        max_anomalies = request.args.get("max_anomalies", 5000, type=int)
        time_window_seconds = request.args.get("time_window_seconds", 300, type=int)
        min_group = request.args.get("min_group", 2, type=int)

        try:
            db = get_db()
            reports = db.get_recent_reports(hours=hours)
            anomaly_reports = [r for r in reports if r.anomaly.is_anomaly]

            if max_anomalies and len(anomaly_reports) > max_anomalies:
                anomaly_reports = sorted(anomaly_reports, key=lambda x: x.anomaly.confidence, reverse=True)[:max_anomalies]

            root_causes = build_root_causes(
                anomaly_reports,
                time_window_seconds=time_window_seconds,
                min_group_size=min_group,
            )
            patterns = detect_patterns(anomaly_reports)
            relationships = map_relationships(anomaly_reports)
            incidents = build_incidents(
                reports=anomaly_reports,
                root_causes=root_causes,
                patterns=patterns,
                relationships=relationships,
            )
            story = build_system_story(incidents=incidents, patterns=patterns, period_hours=hours)

            return jsonify({"story": story, "incident_count": len(incidents)}), 200
        except Exception as e:
            logger.exception("Analysis story failed")
            return jsonify({"error": "Analysis story failed", "detail": str(e)}), 500

    @app.route("/analysis/root-causes", methods=["GET"])
    def analysis_root_causes_endpoint():
        """Get enriched root-cause groups (cluster/time/entity-aware)."""
        hours = request.args.get("hours", 24, type=int)
        max_anomalies = request.args.get("max_anomalies", 5000, type=int)
        time_window_seconds = request.args.get("time_window_seconds", 300, type=int)
        min_group = request.args.get("min_group", 2, type=int)

        try:
            db = get_db()
            reports = db.get_recent_reports(hours=hours)
            anomaly_reports = [r for r in reports if r.anomaly.is_anomaly]

            if max_anomalies and len(anomaly_reports) > max_anomalies:
                anomaly_reports = sorted(anomaly_reports, key=lambda x: x.anomaly.confidence, reverse=True)[:max_anomalies]

            root_causes = build_root_causes(
                anomaly_reports,
                time_window_seconds=time_window_seconds,
                min_group_size=min_group,
            )
            return jsonify([rc.to_dict() for rc in root_causes]), 200
        except Exception as e:
            logger.exception("Analysis root-causes failed")
            return jsonify({"error": "Analysis root-causes failed", "detail": str(e)}), 500

    @app.route("/analysis/patterns", methods=["GET"])
    def analysis_patterns_endpoint():
        """Get behavioral pattern insights derived from anomaly-flagged logs."""
        hours = request.args.get("hours", 24, type=int)
        max_anomalies = request.args.get("max_anomalies", 5000, type=int)

        try:
            db = get_db()
            reports = db.get_recent_reports(hours=hours)
            anomaly_reports = [r for r in reports if r.anomaly.is_anomaly]

            if max_anomalies and len(anomaly_reports) > max_anomalies:
                anomaly_reports = sorted(anomaly_reports, key=lambda x: x.anomaly.confidence, reverse=True)[:max_anomalies]

            patterns = detect_patterns(anomaly_reports)
            return jsonify([p.to_dict() for p in patterns]), 200
        except Exception as e:
            logger.exception("Analysis patterns failed")
            return jsonify({"error": "Analysis patterns failed", "detail": str(e)}), 500

    @app.route("/analysis/clusters", methods=["GET"])
    def analysis_clusters_endpoint():
        """Get similarity clusters distribution (chart-ready)."""
        hours = request.args.get("hours", 24, type=int)

        try:
            insight_engine = InsightEngine()
            insight_payload = insight_engine.get_overview_charts(hours=hours)
            charts = insight_payload.get("charts", {})
            return jsonify({
                "clusters": charts.get("cluster_distribution", []),
                "metrics": insight_payload.get("metrics", {}),
            }), 200
        except Exception as e:
            logger.exception("Analysis clusters failed")
            return jsonify({"error": "Analysis clusters failed", "detail": str(e)}), 500

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

        # Phase 5: Upgrade explanations with batch context (clusters/patterns/root causes).
        # This keeps the system deterministic (no LLM) while providing richer UX fields.
        try:
            upgraded = upgrade_explanations(reports)
            for r in reports:
                if r.log_entry.line_number in upgraded:
                    r.explanation = upgraded[r.log_entry.line_number]
        except Exception:
            # Never fail analysis because of explanation upgrades.
            logger.exception("Deep explanation upgrade failed; falling back to template explanations")

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
