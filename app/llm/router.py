import json
import re
import os
import logging
import time
from datetime import datetime
from typing import List, Dict, Any

# Configure logging based on environment
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
DEV_MODE = os.environ.get('DEV_MODE', '0') == '1'

# Create logger with detailed formatting
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Create detailed formatter for development
if DEV_MODE:
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
else:
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

# Add console handler if not already present
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Use new google.genai package (not deprecated google.generativeai)
try:
    from google import genai
    from google.genai import types
    USE_NEW_GEMINI = True
except ImportError:
    USE_NEW_GEMINI = False
    try:
        import google.generativeai as genai
        logger.warning("Using deprecated google.generativeai package. Please install google-genai.")
    except ImportError:
        genai = None

from groq import Groq

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

MASTER_SYSTEM_PROMPT = """
You are LogVision, an AI-powered observability and log intelligence assistant designed to operate with the reasoning quality of an experienced Site Reliability Engineer (SRE).

Your role is to transform raw logs into operational understanding, root cause hypotheses, risk assessment, and actionable engineering insight.

Your purpose is not simply to summarize logs, but to help engineers understand system behavior, identify meaningful signals, and determine practical next steps.

PRIMARY OBJECTIVE
Logs are not the final product — insight is the final product.

Every response must reduce uncertainty and help the user quickly understand:

• what is happening in the system
• why it is happening
• how serious the situation is
• what evidence supports the conclusion
• what actions may resolve or mitigate the issue
• how confident the reasoning is

Your reasoning should shorten investigation time and reduce cognitive load.

You behave like a calm, precise, analytical reliability engineer.

Avoid generic explanations that are not grounded in the provided logs.

Avoid educational filler unless the user explicitly asks for explanation.

Focus on practical understanding of system behavior.

--------------------------------------------------

RESPONSE CHARACTERISTICS

Responses must feel:

• analytical
• evidence-based
• technically practical
• concise but complete
• calm and professional
• consistent in tone
• focused on useful insight

Avoid exaggerated language.

Avoid repeating identical phrasing across analyses.

Avoid unnecessary verbosity.

Do not produce long generic cybersecurity explanations unless directly supported by log evidence.

--------------------------------------------------

REASONING APPROACH

Interpret logs as signals of system behavior.

Identify meaningful patterns such as:

• repeating failure signatures
• unusual error frequency
• severity imbalance
• dependency failures
• configuration mismatches
• permission problems
• connection instability
• resource constraints
• service startup failures
• unexpected state transitions
• correlation between components
• temporal clustering of failures

Where appropriate, infer relationships between signals.

Example causal reasoning pattern:

configuration inconsistency
→ dependency resolution failure
→ authentication breakdown
→ database connection instability

Prefer probabilistic reasoning over rigid conclusions when evidence is incomplete.

Clearly communicate uncertainty when necessary.

--------------------------------------------------

EVIDENCE-AWARE ANALYSIS

Important claims should reference observable evidence patterns derived from logs, such as:

• recurring log signatures
• frequency spikes
• repeated stack traces
• clustered timestamps
• dominant failure categories
• component-level concentration
• unusual severity ratios

When helpful, reference representative log fragments to clarify reasoning.

Do not dump excessive raw logs.

Surface only meaningful supporting evidence.

Evidence should strengthen clarity, not overwhelm the user.

--------------------------------------------------

STRUCTURE GUIDELINE (FLEXIBLE)

Structure responses naturally based on the situation.

Do not follow a rigid template.

Common useful sections may include:

Key Insight
Primary Issue
Observed Behavior
Supporting Evidence
Impact Interpretation
Root Cause Hypothesis
Recommended Investigation Direction
Suggested Remediation Direction
Confidence Explanation

Include only sections that improve clarity.

Shorter responses are acceptable when signals are simple.

More structured responses are appropriate when signals are complex.

Avoid unnecessary headings.

Avoid repetitive structure across different analyses.

--------------------------------------------------

ACTIONABLE ENGINEERING GUIDANCE

When logs suggest operational issues, provide practical direction that helps engineers determine next steps.

Guidance should indicate areas to inspect rather than overly prescriptive commands.

Examples of useful guidance:

• configuration inconsistencies
• environment mismatches
• dependency misalignment
• connection failures
• credential problems
• unavailable services
• incorrect endpoints
• permission issues
• missing runtime resources
• container misconfiguration
• version incompatibility
• initialization order problems
• service registry inconsistencies

When relevant, suggest verification steps that help confirm hypotheses.

Avoid hallucinating specific file paths or commands when evidence is insufficient.

Recommendations should remain grounded in observed signals.

--------------------------------------------------

CONFIDENCE EXPRESSION

Confidence should reflect strength of evidence.

Confidence may depend on:

• consistency of log patterns
• repetition frequency
• clarity of failure signatures
• number of affected components
• severity level concentration
• correlation strength between events

When confidence is moderate or low, clearly indicate uncertainty.

Confidence explanations help users evaluate reliability of conclusions.

--------------------------------------------------

VISUAL SIGNAL AWARENESS

Where possible, express signals that support visual summarization.

Examples of useful signals:

• dominant error categories
• severity distribution patterns
• recurring failure clusters
• component concentration
• anomaly intensity
• frequency imbalance
• timeline irregularities

These signals help generate meaningful visual summaries.

Do not fabricate numerical values.

Only express signals supported by log evidence.

If data is insufficient, omit the signal.

--------------------------------------------------

CONTEXT-AWARE DEPTH CONTROL

Adjust depth based on strength of signals.

Minimal logs → concise insight.

Strong anomalies → deeper reasoning.

Complex multi-component failures → structured diagnostic explanation.

Avoid verbosity when signals are weak.

Avoid oversimplification when signals are strong.

--------------------------------------------------

CONSISTENCY AND RELIABILITY

Maintain consistent analytical tone across all responses.

Avoid dramatic or exaggerated language.

Avoid speculation without evidence.

Clearly separate observed behavior from inferred reasoning.

Make reasoning transparent and understandable.

Your role is to act as a reasoning partner that helps engineers interpret system behavior and identify meaningful next steps.

--------------------------------------------------

OUTPUT QUALITY STANDARD

Responses should resemble the reasoning quality expected from:

• experienced SRE engineers
• observability platform assistants
• incident analysis tools
• reliability diagnostics systems

The system should feel dependable, thoughtful, and technically credible.

--------------------------------------------------

FINAL PRINCIPLE

Clarity over verbosity.
Evidence over assumption.
Insight over description.
Guidance over explanation.
"""

class LLMRouter:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        
        if not self.gemini_key and not self.groq_key:
            raise Exception("No API keys configured")

        self.gemini_client = None
        if self.gemini_key:
            try:
                if USE_NEW_GEMINI:
                    # New google.genai API
                    self.gemini_client = genai.Client(api_key=self.gemini_key)
                    logger.info("Initialized Gemini with new google.genai package")
                else:
                    # Legacy API
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=self.gemini_key)
                    self.gemini_model = legacy_genai.GenerativeModel('gemini-1.5-flash')
                    logger.info("Initialized Gemini with legacy package")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
                self.gemini_client = None
                self.gemini_model = None
        if self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Detect if an error is a rate limit error."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check for HTTP 429
        if '429' in error_str or 'rate limit' in error_str:
            return True
        
        # Check for quota exceeded
        if 'quota' in error_str and 'exceed' in error_str:
            return True
        
        # Check for too many requests
        if 'too many requests' in error_str:
            return True
        
        return False
    
    def _call_gemini_with_retry(self, prompt, max_retries: int = 1):
        """
        Call Gemini API with retry logic for rate limits.
        
        Args:
            prompt: The prompt to send
            max_retries: Maximum number of retries (default 1)
            
        Returns:
            Response text or raises exception
        """
        for attempt in range(max_retries + 1):
            try:
                if USE_NEW_GEMINI and self.gemini_client:
                    response = self.gemini_client.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=prompt
                    )
                    return response.text
                elif hasattr(self, 'gemini_model') and self.gemini_model:
                    response = self.gemini_model.generate_content(prompt)
                    return response.text
                else:
                    raise Exception("Gemini not properly initialized")
            except Exception as e:
                if self._is_rate_limit_error(e) and attempt < max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    backoff_time = 2 ** attempt
                    logger.warning(f"Rate limit detected on Gemini (attempt {attempt + 1}), "
                                 f"retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
                else:
                    # Not a rate limit or max retries exceeded
                    raise
    
    def _call_gemini(self, prompt):
        """Call Gemini API using new google.genai package or fallback."""
        if USE_NEW_GEMINI and self.gemini_client:
            # New API: use generate_content with client
            response = self.gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            return response.text
        elif hasattr(self, 'gemini_model') and self.gemini_model:
            # Legacy API
            response = self.gemini_model.generate_content(prompt)
            return response.text
        else:
            raise Exception("Gemini not properly initialized")

    def _call_groq(self, prompt):
        # Use a highly capable open model on Groq
        chat_completion = self.groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        return chat_completion.choices[0].message.content

    def _route_hybrid(self, prompt):
        """
        Hybrid routing strategy with rate limit handling.
        
        Strategy:
        1. Try Gemini primary
        2. On rate limit: retry once with exponential backoff
        3. On second failure: fallback to Groq
        4. Preserve conversation context across retries
        """
        import concurrent.futures
        
        # Try Gemini first with retry
        gemini_result = None
        gemini_error = None
        
        try:
            logger.info("Attempting Gemini (primary)")
            gemini_result = self._call_gemini_with_retry(prompt, max_retries=1)
            logger.info("Gemini request successful")
            return {"status": "success", "text": gemini_result, "source": "gemini"}
        except Exception as e:
            gemini_error = e
            if self._is_rate_limit_error(e):
                logger.warning(f"Gemini rate limited after retry: {e}")
            else:
                logger.warning(f"Gemini failed: {e}")
        
        # Fallback to Groq
        if self.groq_key:
            try:
                logger.info("Falling back to Groq")
                groq_result = self._call_groq(prompt)
                logger.info("Groq request successful")
                return {"status": "success", "text": groq_result, "source": "groq"}
            except Exception as e:
                logger.error(f"Groq fallback failed: {e}")
                raise Exception(f"Both LLMs failed - Gemini: {gemini_error}, Groq: {e}")
        else:
            # No Groq available, raise Gemini error
            raise Exception(f"Gemini failed and no Groq fallback available: {gemini_error}")

    def _route_dual(self, prompt):
        """Call both Gemini and Groq simultaneously and merge results for better accuracy."""
        import concurrent.futures
        import json
        
        results = {}
        errors = []
        
        def call_gemini():
            if self.gemini_client or getattr(self, 'gemini_model', None):
                try:
                    return self._call_gemini(prompt)
                except Exception as e:
                    return f"GEMINI_ERROR: {e}"
            return None
            
        def call_groq():
            if self.groq_key:
                try:
                    return self._call_groq(prompt)
                except Exception as e:
                    return f"GROQ_ERROR: {e}"
            return None
        
        # Call both APIs in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            gemini_future = executor.submit(call_gemini)
            groq_future = executor.submit(call_groq)
            
            gemini_result = gemini_future.result(timeout=60)
            groq_result = groq_future.result(timeout=60)
        
        # Check for valid responses
        gemini_valid = gemini_result and not gemini_result.startswith("GEMINI_ERROR")
        groq_valid = groq_result and not groq_result.startswith("GROQ_ERROR")
        
        if gemini_valid and groq_valid:
            # Both succeeded - prefer the one with more structured data
            gemini_data = self._extract_json_resilient(gemini_result) or {}
            groq_data = self._extract_json_resilient(groq_result) or {}
            
            # Count metrics in each response
            gemini_metrics_count = len([v for v in gemini_data.get("metrics", {}).values() if v])
            groq_metrics_count = len([v for v in groq_data.get("metrics", {}).values() if v])
            
            # Use the response with more metrics, or merge them
            if gemini_metrics_count >= groq_metrics_count:
                logger.info("Using Gemini response (more metrics)")
                return {"status": "success", "text": gemini_result, "source": "gemini"}
            else:
                logger.info("Using Groq response (more metrics)")
                return {"status": "success", "text": groq_result, "source": "groq"}
                
        elif gemini_valid:
            logger.info("Using Gemini response (Groq failed)")
            return {"status": "success", "text": gemini_result, "source": "gemini"}
            
        elif groq_valid:
            logger.info("Using Groq response (Gemini failed)")
            return {"status": "success", "text": groq_result, "source": "groq"}
            
        else:
            raise Exception(f"Both LLMs failed - Gemini: {gemini_result}, Groq: {groq_result}")

    def _route(self, prompt):
        # Use hybrid routing with rate limit handling
        return self._route_hybrid(prompt)
    
    def _prepare_logs_for_llm(self, logs: str, max_chars: int = 12000) -> str:
        """
        Prepare logs for LLM analysis using progressive summarization.
        
        Instead of naive truncation, this method:
        1. Extracts structured signals
        2. Prioritizes error/warning lines
        3. Maintains distribution awareness
        4. Preserves key log snippets as evidence
        
        Args:
            logs: Raw log string
            max_chars: Maximum characters to include in prompt
            
        Returns:
            Prepared log string for LLM
        """
        try:
            from app.processing.chunk_processor import ChunkProcessor
            from app.processing.signal_extractor import SignalExtractor
        except ImportError:
            # Fallback to simple truncation if modules not available
            logger.warning("Chunk processor or signal extractor not available, using simple truncation")
            return logs[:max_chars]
        
        log_lines = logs.split('\n')
        
        # If logs are small enough, return as-is
        if len(logs) < 100 and len(logs) < max_chars:
            return logs
        
        # Extract structured signals
        signal_extractor = SignalExtractor()
        signals = signal_extractor.extract_signals(log_lines)
        
        # Extract key log snippets for evidence
        key_snippets = signal_extractor.extract_key_log_snippets(log_lines, count=15)
        
        # Build prepared logs with signals
        prepared_parts = []
        
        # Add signal summary
        signal_summary = f"""=== LOG ANALYSIS CONTEXT ===
Total Lines: {signals['total_lines']}
Severity Distribution: {signals['severity_distribution']}
Top Components: {[c['name'] for c in signals['components'][:5]]}
Error Pattern Count: {len(signals['error_patterns'])}
Repeating Signatures: {len(signals['repeating_signatures'])}
"""
        prepared_parts.append(signal_summary)
        
        # Add key error/warning lines first (highest priority)
        prepared_parts.append("\n=== KEY ERROR AND WARNING LINES ===")
        for snippet in key_snippets[:10]:
            prepared_parts.append(snippet)
        
        # Add component-specific error clusters
        prepared_parts.append("\n=== COMPONENT ERROR CLUSTERS ===")
        for component in signals['components'][:5]:
            if component['error_count'] > 0:
                prepared_parts.append(f"\n{component['name']} ({component['error_count']} errors)")
        
        # Add repeating patterns
        if signals['repeating_signatures']:
            prepared_parts.append("\n=== REPEATING PATTERNS ===")
            for pattern in signals['repeating_signatures'][:5]:
                prepared_parts.append(f"Pattern (appears {pattern['count']} times, {pattern['percentage']}%):")
                prepared_parts.append(pattern['signature'])
        
        # Add additional context lines if space remains
        prepared_parts.append("\n=== ADDITIONAL CONTEXT ===")
        # Add some normal lines to maintain distribution
        normal_lines = [line for line in log_lines if not any(
            kw in line.upper() for kw in ['ERROR', 'WARN', 'FATAL', 'CRITICAL']
        )]
        for line in normal_lines[:20]:
            prepared_parts.append(line)
        
        # Combine and truncate to max_chars
        prepared = '\n'.join(prepared_parts)
        
        if len(prepared) > max_chars:
            # Truncate from the end, preserving the beginning
            prepared = prepared[:max_chars] + "\n... (truncated)"
        
        logger.info(f"Prepared logs for LLM: {len(logs)} lines -> {len(prepared)} chars")
        
        return prepared
        
    def _extract_metrics_from_markdown(self, markdown, logs):
        """Parse metrics from markdown narrative when JSON parsing fails."""
        import re
        metrics = {
            "total_logs": len([l for l in logs.split('\n') if l.strip()]),
            "error_rate": 0,
            "anomaly_score": 50,
            "severity_distribution": [],
            "affected_components": [],
            "pattern_counts": [],
            "timeline_data": []
        }
        
        # Count severity levels from logs directly
        error_count = len(re.findall(r'\bERROR\b|\bFATAL\b|\bCRITICAL\b', logs, re.IGNORECASE))
        warn_count = len(re.findall(r'\bWARN\b|\bWARNING\b', logs, re.IGNORECASE))
        info_count = len(re.findall(r'\bINFO\b', logs, re.IGNORECASE))
        fatal_count = len(re.findall(r'\bFATAL\b', logs, re.IGNORECASE))
        
        if error_count or warn_count or info_count or fatal_count:
            metrics["severity_distribution"] = [
                {"level": "ERROR", "count": error_count},
                {"level": "WARN", "count": warn_count},
                {"level": "INFO", "count": info_count},
                {"level": "FATAL", "count": fatal_count}
            ]
        
        # Extract component failures from markdown patterns like "- ServiceName: X errors"
        component_pattern = r'[-*]?\s*\[?(\w+)\]?:\s*(\d+)\s+(?:error|failure|issue)'
        for match in re.finditer(component_pattern, markdown, re.IGNORECASE):
            component = match.group(1)
            count = int(match.group(2))
            metrics["affected_components"].append({
                "component": component,
                "failures": count,
                "severity": "HIGH" if count > 5 else "MEDIUM" if count > 2 else "LOW"
            })
        
        # If no components found in markdown, extract from log brackets like [AuthService]
        if not metrics["affected_components"]:
            service_pattern = r'\[(\w+)\]'
            services = {}
            for match in re.finditer(service_pattern, logs):
                service = match.group(1)
                services[service] = services.get(service, 0) + 1
            for service, count in services.items():
                if count > 0:
                    metrics["affected_components"].append({
                        "component": service,
                        "failures": count,
                        "severity": "HIGH" if count > 5 else "MEDIUM" if count > 2 else "LOW"
                    })
        
        # Calculate error rate
        total = metrics["total_logs"]
        if total > 0:
            metrics["error_rate"] = round((error_count + fatal_count) / total * 100, 1)
        
        # Calculate anomaly score based on error density
        if metrics["error_rate"] > 50:
            metrics["anomaly_score"] = 85
        elif metrics["error_rate"] > 20:
            metrics["anomaly_score"] = 65
        elif error_count > 0:
            metrics["anomaly_score"] = 45
        else:
            metrics["anomaly_score"] = 20
        
        return metrics

    def _extract_json_resilient(self, text):
        """Extract JSON from text with multiple fallback strategies."""
        # Strategy 1: Clean and parse directly
        try:
            clean_text = text.strip()
            if clean_text.startswith('{') and clean_text.endswith('}'):
                return json.loads(clean_text)
        except:
            pass
        
        # Strategy 2: Extract JSON object from surrounding text
        try:
            start_idx = text.find('{')
            if start_idx == -1:
                return None
            end_idx = text.rfind('}')
            if end_idx == -1 or end_idx <= start_idx:
                return None
            
            json_text = text[start_idx:end_idx+1]
            return json.loads(json_text)
        except:
            pass
        
        # Strategy 3: Extract with markdown code blocks
        try:
            # Remove markdown code block markers
            cleaned = text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            if cleaned.startswith('{') and cleaned.endswith('}'):
                return json.loads(cleaned)
        except:
            pass
        
        # Strategy 4: Try to fix common JSON issues
        try:
            # Remove trailing commas, fix quotes, etc.
            fixed_text = text.strip()
            # Remove any text before the first {
            start_idx = fixed_text.find('{')
            if start_idx != -1:
                fixed_text = fixed_text[start_idx:]
            # Remove any text after the last }
            end_idx = fixed_text.rfind('}')
            if end_idx != -1:
                fixed_text = fixed_text[:end_idx+1]
            
            # Fix common issues
            fixed_text = re.sub(r',\s*}', '}', fixed_text)  # Remove trailing commas
            fixed_text = re.sub(r',\s*]', ']', fixed_text)  # Remove trailing commas in arrays
            
            return json.loads(fixed_text)
        except:
            pass
        
        return None

    def _normalize_response_structure(self, data):
        """Normalize response structure to handle schema variations."""
        normalized = {
            "insights": [],
            "root_causes": [],
            "evidence": [],
            "fixes": {"commands": [], "config_changes": []},
            "security_analysis": {},
            "patterns": [],
            "metrics": {},
            "confidence": 50,
            "narrative_markdown": "",
            
            # SRE Intelligence fields
            "key_insight": "",
            "core_problem": {},
            "causal_chain": [],
            "impact_assessment": {},
            "root_cause_hypothesis": {},
            "recommended_actions": [],
            "confidence_explanation": "",
            "risk_level": "UNKNOWN"
        }
        
        # Copy valid fields
        for key, default_value in normalized.items():
            if key in data and data[key] is not None:
                if isinstance(default_value, dict) and isinstance(data[key], dict):
                    normalized[key].update(data[key])
                elif isinstance(default_value, list) and isinstance(data[key], list):
                    normalized[key] = data[key]
                else:
                    normalized[key] = data[key]
        
        # Handle legacy field names
        if "key_findings" in data and not normalized["insights"]:
            normalized["insights"] = data["key_findings"]
            
        # SRE fields fallbacks
        if not normalized["key_insight"] and normalized["insights"] and len(normalized["insights"]) > 0:
            if isinstance(normalized["insights"][0], dict):
                normalized["key_insight"] = normalized["insights"][0].get("title", "")
                
        if "risk_level" in data:
             normalized["risk_level"] = data["risk_level"]
        elif "core_problem" in data and "severity" in data["core_problem"]:
             normalized["risk_level"] = data["core_problem"]["severity"]
        
        if "anomalies" in data and not normalized["patterns"]:
            normalized["patterns"] = data["anomalies"]
        
        if "risk_level" in data and not normalized["security_analysis"]:
            normalized["security_analysis"]["threat_level"] = data["risk_level"]
        
        # Extract narrative from various field names
        narrative_fields = ["narrative_markdown", "chat_response", "chat_markdown", "summary"]
        for field in narrative_fields:
            if field in data and data[field]:
                normalized["narrative_markdown"] = data[field]
                break
        
        return normalized

    def generate_analysis(self, payload_context, instruction="", *args, **kwargs):
        logger.info(f"🚀 Starting analysis with instruction: '{instruction}'")
        start_time = time.time()
        
        import json
        import re

        if isinstance(payload_context, str):
            logs = payload_context
            parsed_context = {"raw_logs_snippet": logs[:5000]}
            logger.debug(f"Received string input, {len(logs)} characters")
        else:
            logs = payload_context.get("raw_logs", "")
            parsed_context = payload_context
            logger.debug(f"Received dict input, {len(logs)} characters in logs")
        
        logger.debug(f"Log sample: {logs[:200]}...")

        # Enhanced heuristics detection for actionable fixes
        logger.debug("🔍 Starting heuristics detection")
        heuristics_found = []
        actionable_patterns = []

        # Port conflict detection
        port_match = re.search(r"Address already in use.*?:(\d+)", logs, re.IGNORECASE)
        if port_match:
            port = port_match.group(1)
            heuristics_found.append({"pattern": "Address already in use", "inference": "port conflict", "port": port})
            actionable_patterns.append({
                "type": "port_conflict",
                "port": port,
                "commands": [
                    f"lsof -i :{port}",
                    f"kill -9 <PID>",
                    f"netstat -tulpn | grep :{port}"
                ]
            })

        # Timeout issues
        if re.search(r"timeout|timed out", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "timeout", "inference": "network latency issue"})
            actionable_patterns.append({
                "type": "timeout",
                "commands": [
                    "ping -c 4 8.8.8.8",
                    "curl -I --connect-timeout 5 http://example.com",
                    "ss -tuln"
                ]
            })

        # Permission denied
        if re.search(r"permission denied|access denied|Operation not permitted", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "permission denied", "inference": "access control problem"})
            actionable_patterns.append({
                "type": "permission",
                "commands": [
                    "ls -la /path/to/file",
                    "chmod 644 /path/to/file",
                    "chown user:group /path/to/file",
                    "sudo chmod +x /path/to/script"
                ]
            })

        # Connection refused
        if re.search(r"connection refused|can't connect|failed to connect", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "connection refused", "inference": "service offline"})
            actionable_patterns.append({
                "type": "connection",
                "commands": [
                    "systemctl status service-name",
                    "netstat -tulpn",
                    "ss -tulpn",
                    "docker ps"
                ]
            })

        # Missing dependencies
        if re.search(r"module not found|no module named|import error", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "missing dependency", "inference": "package missing"})
            actionable_patterns.append({
                "type": "dependency",
                "commands": [
                    "pip install missing-package",
                    "npm install missing-package",
                    "apt-get install package-name"
                ]
            })

        # Disk space issues
        if re.search(r"no space left|disk full|out of space", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "disk space", "inference": "storage exhausted"})
            actionable_patterns.append({
                "type": "disk_space",
                "commands": [
                    "df -h",
                    "du -sh /path/*",
                    "find /path -type f -size +100M",
                    "ls -la /tmp"
                ]
            })

        # Memory issues
        if re.search(r"out of memory|cannot allocate|memory exhausted", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "memory", "inference": "memory exhaustion"})
            actionable_patterns.append({
                "type": "memory",
                "commands": [
                    "free -h",
                    "ps aux --sort=-%mem | head",
                    "top -o %MEM",
                    "dmesg | grep -i memory"
                ]
            })

        # Detect user intent from instruction
        user_intent = "general"
        if any(keyword in instruction.lower() for keyword in ["fix", "solve", "resolve", "repair"]):
            user_intent = "fix"
        elif any(keyword in instruction.lower() for keyword in ["security", "vulnerability", "attack", "breach"]):
            user_intent = "security"
        elif any(keyword in instruction.lower() for keyword in ["anomaly", "unusual", "strange", "weird"]):
            user_intent = "anomaly"
        elif any(keyword in instruction.lower() for keyword in ["monitor", "watch", "track"]):
            user_intent = "monitoring"

        # Enhanced context with actionable patterns
        context_to_llm = {
            "heuristics_found": heuristics_found,
            "actionable_patterns": actionable_patterns,
            "user_intent": user_intent,
            "instruction": instruction,
            "selected_features": parsed_context.get("features", []),
            "parsed_statistics": parsed_context.get("stats", {}),
            "anomalies": parsed_context.get("anomalies", [])[:20],
            "severity_scores": parsed_context.get("severity_distribution", {}),
            "raw_logs_snippet": logs[:5000]
        }
        
        prompt = f"""{MASTER_SYSTEM_PROMPT}

ANALYSIS METHODOLOGY:
1. SCAN every log line — count entries, extract components, identify temporal patterns
2. IDENTIFY anomalous patterns — error clustering, severity spikes, unusual sequences
3. CONSTRUCT causal chains — trace failure propagation across components
4. ASSESS impact — determine blast radius and affected services
5. FORMULATE root cause hypothesis — with explicit confidence and evidence
6. PRESCRIBE targeted actions — specific, prioritized, with rationale

CRITICAL RULES:
- Reference ONLY patterns found in the actual logs — never fabricate evidence
- Every claim must cite specific log evidence
- Quantify everything: counts, percentages, rates
- If evidence is insufficient for a strong conclusion, say so explicitly
- Prefer precision over breadth — a focused analysis beats a generic one

REQUIRED OUTPUT — Valid JSON only:
{{{{
  "key_insight": "One-sentence executive summary of the most important finding",
  "core_problem": {{{{
    "title": "Concise problem statement",
    "description": "What is happening and why it matters",
    "evidence": ["Exact log lines or patterns that reveal this problem"],
    "severity": "LOW|MEDIUM|HIGH|CRITICAL"
  }}}},
  "causal_chain": [
    {{{{"step": 1, "event": "Initial trigger or root cause", "evidence": "supporting log fragment", "component": "ServiceName"}}}},
    {{{{"step": 2, "event": "Cascading effect", "evidence": "supporting log fragment", "component": "ServiceName"}}}},
    {{{{"step": 3, "event": "Resulting failure", "evidence": "supporting log fragment", "component": "ServiceName"}}}}
  ],
  "impact_assessment": {{{{
    "blast_radius": "Description of how many and which components are affected",
    "affected_components": [{{{{"component": "Name", "impact": "Description", "error_count": 0}}}}],
    "user_impact": "How this affects end users or system reliability",
    "stability_score": 0
  }}}},
  "root_cause_hypothesis": {{{{
    "hypothesis": "Most likely root cause based on evidence",
    "confidence": 75,
    "supporting_evidence": ["Evidence supporting this hypothesis"],
    "uncertainties": ["What we don't know or can't confirm from these logs"],
    "alternative_hypotheses": ["Other possible causes worth investigating"]
  }}}},
  "recommended_actions": [
    {{{{"priority": 1, "action": "Most important action to take", "rationale": "Why this helps", "command": "Optional CLI command"}}}},
    {{{{"priority": 2, "action": "Secondary action", "rationale": "Why", "command": "optional"}}}}
  ],
  "confidence_explanation": "Plain-language explanation of overall analysis confidence — what evidence is strong, what is uncertain",
  "insights": [
    {{{{
      "title": "Finding title",
      "description": "Factual observation based on evidence",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "confidence": 75,
      "evidence": ["Log lines supporting this"]
    }}}}
  ],
  "metrics": {{{{
    "total_logs": 0,
    "error_rate": 0.0,
    "anomaly_score": 0,
    "severity_distribution": [
      {{{{"level": "ERROR", "count": 0}}}},
      {{{{"level": "WARN", "count": 0}}}},
      {{{{"level": "INFO", "count": 0}}}},
      {{{{"level": "FATAL", "count": 0}}}}
    ],
    "affected_components": [
      {{{{"component": "Name", "failures": 0, "severity": "HIGH"}}}}
    ],
    "pattern_counts": [
      {{{{"pattern": "Error pattern description", "count": 0}}}}
    ],
    "timeline_data": [
      {{{{"time": "HH:MM", "errors": 0}}}}
    ]
  }}}},
  "root_causes": [
    {{{{
      "issue": "Root cause title",
      "evidence": ["Supporting log lines"],
      "impact": "What this affects",
      "recommendation": "Specific fix"
    }}}}
  ],
  "fixes": {{{{
    "commands": [
      {{{{"command": "fix command", "purpose": "What it addresses", "explanation": "Why it helps"}}}}
    ]
  }}}},
  "security_analysis": {{{{
    "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "indicators": ["Security indicators found"]
  }}}},
  "narrative_markdown": "## Key Insight\\n\\n[1-2 sentence executive summary]\\n\\n## Core Problem\\n\\n[Evidence-backed description]\\n\\n## Failure Chain\\n\\n[Step-by-step failure propagation]\\n\\n## Impact\\n\\n[Blast radius and affected components]\\n\\n## Root Cause\\n\\n[Hypothesis with confidence]\\n\\n## Recommended Actions\\n\\n[Prioritized action items]\\n\\n## Evidence\\n\\n```\\n[Key log lines]\\n```\\n\\n## Confidence\\n\\n[Explanation of reasoning confidence]"
}}}}

LOGS TO ANALYZE:
{self._prepare_logs_for_llm(logs, max_chars=12000)}

{f'User Focus: {instruction}' if instruction else 'Provide comprehensive analysis.'}

OUTPUT: Return ONLY the JSON object. No markdown wrappers. No commentary."""
        res = self._route(prompt)
        text = res.get("text", "")
        
        # Clean up possible markdown code blocks around JSON
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Try to extract the JSON object if there's any surrounding text
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx+1]

        try:
            # Use resilient JSON extraction
            parsed = self._extract_json_resilient(text)
            logger.info(f"JSON extraction result: {parsed is not None}")
            
            if parsed:
                # Normalize the structure to handle variations
                normalized_response = self._normalize_response_structure(parsed)
                
                # Check if metrics are empty - if so, extract from logs
                metrics = normalized_response.get("metrics", {})
                logger.info(f"Metrics from LLM: {metrics}")
                has_valid_metrics = any(v for v in metrics.values() if v not in (None, [], {}, 0, ""))
                logger.info(f"Has valid metrics: {has_valid_metrics}")
                
                if not metrics or not has_valid_metrics:
                    logger.info("Metrics empty in LLM response, extracting from logs directly")
                    narrative = normalized_response.get("narrative_markdown", text)
                    logger.info(f"Narrative length: {len(narrative) if narrative else 0}")
                    extracted_metrics = self._extract_metrics_from_markdown(narrative, logs)
                    logger.info(f"Extracted metrics: {extracted_metrics}")
                    normalized_response["metrics"] = extracted_metrics
                
                # Enhanced response processing with evidence validation
                processed_response = self._process_adaptive_response(normalized_response, logs, actionable_patterns)
                
                # Ensure narrative_markdown exists and is proper markdown
                narrative = processed_response.get("narrative_markdown", "")
                if not narrative or narrative.strip().startswith("{"):
                    # Generate narrative from structured data if missing
                    narrative = self._build_adaptive_markdown(processed_response)
                    processed_response["narrative_markdown"] = narrative
                
                # Add quality metrics
                processed_response["quality_metrics"] = self._assess_response_quality(processed_response, logs)
                
                return {"status": "success", "summary": processed_response}
            else:
                # JSON extraction failed - parse metrics from markdown and logs directly
                logger.warning("JSON parsing failed, extracting metrics from markdown and logs")
                
                # Extract metrics from the markdown content and raw logs
                extracted_metrics = self._extract_metrics_from_markdown(text, logs)
                
                # Try to extract any markdown content for the narrative
                narrative = text
                if text.startswith('{') or 'narrative_markdown' in text:
                    # Try to extract narrative from JSON-like content
                    narrative_match = re.search(r'"narrative_markdown"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
                    if narrative_match:
                        narrative = narrative_match.group(1).replace("\\n", "\n").replace('\\"', '"')
                
                # Build response with extracted metrics
                return {"status": "success", "summary": {
                    "narrative_markdown": narrative if narrative else self._generate_fallback_response(logs, actionable_patterns, user_intent),
                    "metrics": extracted_metrics,
                    "insights": [],
                    "root_causes": [],
                    "evidence": [],
                    "fixes": {"commands": [], "config_changes": []},
                    "confidence": 60,
                    "parsing_fallback": True  # Flag indicating we extracted from logs directly
                }}
                
        except Exception as e:
            # Ultimate fallback - always provide useful output with extracted metrics
            logger.error(f"Response processing error: {e}")
            fallback_md = self._generate_fallback_response(logs, actionable_patterns, user_intent)
            extracted_metrics = self._extract_metrics_from_markdown(fallback_md, logs)
            
            return {"status": "success", "summary": {
                "narrative_markdown": fallback_md,
                "metrics": extracted_metrics,
                "insights": [],
                "root_causes": [],
                "evidence": [],
                "fixes": {"commands": [], "config_changes": []},
                "confidence": 40,
                "processing_error": str(e)
            }}

    def _process_adaptive_response(self, parsed, logs, actionable_patterns):
        """Process and enhance the adaptive response with actionable patterns."""
        processed = parsed.copy()
        
        # Merge detected actionable patterns with AI-generated fixes
        existing_fixes = processed.get("fixes", {})
        if not existing_fixes:
            existing_fixes = {"commands": [], "config_changes": []}
        
        # Add our heuristics-detected commands if not already present
        for pattern in actionable_patterns:
            for cmd in pattern.get("commands", []):
                cmd_exists = any(
                    existing_cmd.get("command", "") == cmd 
                    for existing_cmd in existing_fixes.get("commands", [])
                )
                if not cmd_exists:
                    existing_fixes["commands"].append({
                        "purpose": f"Address {pattern['type']} issue",
                        "command": cmd,
                        "explanation": f"Detected {pattern['type']} pattern in logs"
                    })
        
        processed["fixes"] = existing_fixes
        
        # Extract and enhance evidence
        evidence = processed.get("evidence", [])
        if not evidence and logs:
            # Auto-extract key log lines as evidence if AI didn't provide any
            lines = logs.split('\n')[:10]  # First 10 lines
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ["error", "failed", "exception", "critical"]):
                    evidence.append({
                        "log_line": line.strip(),
                        "line_number": i + 1,
                        "significance": "Contains error indicator"
                    })
        processed["evidence"] = evidence
        
        return processed
    
    def _build_adaptive_markdown(self, data):
        """Build adaptive markdown from structured data based on content."""
        parts = []
        
        # Title based on user intent and content
        insights = data.get("insights", [])
        fixes = data.get("fixes", {})
        root_causes = data.get("root_causes", [])
        security = data.get("security_analysis", {})
        patterns = data.get("patterns", [])
        
        # Lead with most relevant section
        if fixes.get("commands") and any(cmd.get("command") for cmd in fixes["commands"]):
            parts.append("# Key Insight")
            parts.append("Fixable issues detected in your logs. Below are specific commands to resolve them.")
            
            parts.append("\n## Recommended Fixes")
            for cmd in fixes["commands"]:
                if cmd.get("command"):
                    purpose = cmd.get("purpose", "System fix")
                    explanation = cmd.get("explanation", "")
                    parts.append(f"**{purpose}**")
                    parts.append(f"```bash\n{cmd['command']}\n```")
                    if explanation:
                        parts.append(f"*{explanation}*")
                    parts.append("")
        
        if security and security.get("indicators"):
            parts.append("## Security Analysis")
            threat_level = security.get("threat_level", "UNKNOWN")
            parts.append(f"**Threat Level: {threat_level}**")
            for indicator in security.get("indicators", []):
                parts.append(f"- {indicator}")
            parts.append("")
        
        if root_causes:
            parts.append("## Root Cause")
            for rc in root_causes:
                issue = rc.get("issue", "")
                evidence = rc.get("evidence", [])
                impact = rc.get("impact", "")
                recommendation = rc.get("recommendation", "")
                
                parts.append(f"**{issue}**")
                if impact:
                    parts.append(f"Impact: {impact}")
                if evidence:
                    parts.append("Evidence:")
                    for ev in evidence[:2]:  # Limit to top 2
                        parts.append(f"- `{ev}`")
                if recommendation:
                    parts.append(f"Fix: {recommendation}")
                parts.append("")
        
        if insights:
            parts.append("## Key Observations")
            for insight in insights:
                title = insight.get("title", "")
                description = insight.get("description", "")
                severity = insight.get("severity", "")
                confidence = insight.get("confidence", "")
                evidence = insight.get("evidence", [])
                
                parts.append(f"**{title}** ({severity}, {confidence}% confidence)")
                parts.append(description)
                if evidence:
                    parts.append("Evidence:")
                    for ev in evidence[:2]:
                        parts.append(f"- `{ev}`")
                parts.append("")
        
        if patterns:
            parts.append("## Detected Patterns")
            for pattern in patterns:
                ptype = pattern.get("type", "")
                description = pattern.get("description", "")
                count = pattern.get("count", 0)
                timeframe = pattern.get("timeframe", "")
                
                parts.append(f"**{ptype.replace('_', ' ').title()}**")
                parts.append(f"{description} (Count: {count}, Timeframe: {timeframe})")
                parts.append("")
        
        # Evidence section
        evidence = data.get("evidence", [])
        if evidence:
            parts.append("## Log Evidence")
            for ev in evidence[:5]:  # Show top 5 evidence items
                line = ev.get("log_line", "")
                significance = ev.get("significance", "")
                parts.append(f"`{line}`")
                if significance:
                    parts.append(f"*{significance}*")
                parts.append("")
        
        confidence = data.get("confidence", "")
        if confidence:
            parts.append(f"## Confidence\n**{confidence}%** - Based on log completeness and pattern clarity")
        
        return "\n".join(parts) if parts else "# Analysis Complete\nNo significant issues detected in the provided logs."
    
    def _assess_response_quality(self, response, logs):
        """Assess response quality based on evidence and specificity."""
        quality = {
            "evidence_score": 0,
            "specificity_score": 0,
            "actionability_score": 0,
            "overall_score": 0
        }
        
        # Evidence scoring
        evidence = response.get("evidence", [])
        if evidence:
            quality["evidence_score"] = min(100, len(evidence) * 20)
        
        # Specificity scoring - check for log references
        narrative = response.get("narrative_markdown", "")
        if logs and narrative:
            log_snippets_in_response = 0
            lines = logs.split('\n')
            for line in lines[:20]:  # Check first 20 lines
                if len(line.strip()) > 10 and line.strip() in narrative:
                    log_snippets_in_response += 1
            quality["specificity_score"] = min(100, log_snippets_in_response * 25)
        
        # Actionability scoring
        fixes = response.get("fixes", {})
        commands = fixes.get("commands", [])
        if commands:
            quality["actionability_score"] = min(100, len(commands) * 30)
        
        # Overall quality
        scores = [quality["evidence_score"], quality["specificity_score"], quality["actionability_score"]]
        quality["overall_score"] = sum(scores) // len(scores) if scores else 0
        
        return quality
    
    def _generate_fallback_response(self, logs, actionable_patterns, user_intent):
        """Generate intelligent fallback response when LLM fails."""
        if actionable_patterns:
            # Use heuristics to provide useful response
            parts = ["# Analysis Results\n"]
            
            for pattern in actionable_patterns[:3]:  # Top 3 patterns
                pattern_type = pattern.get("type", "unknown")
                commands = pattern.get("commands", [])
                
                parts.append(f"## {pattern_type.replace('_', ' ').title()} Detected")
                parts.append(f"Issues related to {pattern_type} found in logs.")
                
                if commands:
                    parts.append("### Recommended Commands:")
                    for cmd in commands[:3]:
                        parts.append(f"```bash\n{cmd}\n```")
                parts.append("")
            
            parts.append("## Confidence\n**70%** - Based on pattern detection")
            return "\n".join(parts)
        
        return """# Analysis Complete

No specific issues detected in the provided logs. The logs appear to be within normal operating parameters.

If you're experiencing specific problems, please:
1. Provide more log context
2. Describe the specific issue you're investigating
3. Include error messages or timestamps

## Confidence
**40%** - Limited log evidence for analysis"""

    def answer_question(self, question, context=None, history=None, *args, **kwargs):
        history_str = ""
        if history:
            history_str = "Chat History:\n" + "\n".join([f"{msg['role']}: {msg['content']}" for msg in history]) + "\n"
        
        # Reuse structured signals from context to avoid reprocessing
        context_str = ""
        if context and context.get("structured_state"):
            state = context["structured_state"]
            context_parts = []
            
            # Add key insight
            if state.get("key_insight"):
                context_parts.append(f"Previous Analysis Summary: {state['key_insight']}")
            
            # Add core problem
            if state.get("core_problem"):
                cp = state["core_problem"]
                context_parts.append(f"Core Problem: {cp.get('title', 'N/A')} - {cp.get('description', 'N/A')}")
            
            # Add causal chain
            if state.get("causal_chain"):
                context_parts.append(f"Failure Chain: {len(state['causal_chain'])} steps identified")
            
            # Add metrics
            if state.get("metrics"):
                metrics = state["metrics"]
                total_logs = metrics.get("total_logs", 0)
                error_rate = metrics.get("error_rate", 0)
                context_parts.append(f"Log Statistics: {total_logs} total lines, {error_rate}% error rate")
            
            # Add components
            if state.get("metrics", {}).get("affected_components"):
                components = state["metrics"]["affected_components"][:5]
                comp_names = [c.get("component", "Unknown") for c in components]
                context_parts.append(f"Affected Components: {', '.join(comp_names)}")
            
            if context_parts:
                context_str = "\n".join(context_parts) + "\n"
        
        prompt = f"""{MASTER_SYSTEM_PROMPT}

You MUST format every response using markdown with this structure:
## Key Insight or Summary
Brief overview of your answer.
## Diagnostic Details 
- Use bullet points for key items
- **Bold** important terms
- Reference actual log patterns when available to support your claims
- Identify any causal chains if relevant
## Recommended Action Items
1. Numbered practical next steps if applicable

Never output plain paragraph blocks or unstructured essay text.
Always be calm, analytical, concise, and reference log evidence when available.

{context_str}
{history_str}
User Question: {question}"""
        res = self._route(prompt)
        return {"status": res["status"], "answer": res.get("text", "")}

def get_llm_router():
    return LLMRouter()
