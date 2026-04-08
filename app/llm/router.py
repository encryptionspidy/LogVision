import json
import re
import os
import logging
import time
from datetime import datetime

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
        # Use dual-LLM strategy for better results
        return self._route_dual(prompt)
        
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
            "narrative_markdown": ""
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
        
        prompt = f"""You are a professional log analysis engine. Your task is to analyze the provided log data and generate a structured, technical report. Do NOT be conversational. Do NOT ask questions. Focus ONLY on factual findings.

CRITICAL RULES:
1. ANALYZE ONLY the actual logs provided - never provide generic explanations
2. COUNT every log entry accurately for metrics
3. EXTRACT service names from bracketed components like [AuthService], [Database]
4. RETURN only valid JSON with all metrics populated from real log data
5. The narrative_markdown must be a TECHNICAL REPORT, not a conversation

REQUIRED OUTPUT FORMAT:
{{
"insights": [
    {{
    "title": "Specific issue found in logs",
    "description": "Factual observation based on log evidence",
    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "confidence": 75,
    "evidence": ["Actual log lines supporting this finding"]
    }}
],
"metrics": {{
    "total_logs": <count every line>,
    "error_rate": <percentage of ERROR+FATAL entries>,
    "anomaly_score": <0-100 based on error density>,
    "severity_distribution": [
        {{"level": "ERROR", "count": <actual count>}},
        {{"level": "WARN", "count": <actual count>}},
        {{"level": "INFO", "count": <actual count>}},
        {{"level": "FATAL", "count": <actual count>}}
    ],
    "affected_components": [
        {{"component": "ExtractedName", "failures": <count>, "severity": "HIGH"}}
    ],
    "pattern_counts": [
        {{"pattern": "Specific error pattern", "count": <actual>}}
    ],
    "timeline_data": [
        {{"time": "HH:MM", "error_count": <count per timeslot>}}
    ]
}},
"root_causes": [
    {{
    "issue": "Specific root cause identified",
    "evidence": ["Log lines showing the cause"],
    "impact": "What this affects",
    "recommendation": "Specific fix command or action"
    }}
],
"fixes": {{
    "commands": [
        {{"command": "specific fix command", "purpose": "What this addresses", "explanation": "Why this helps"}}
    ]
}},
"security_analysis": {{
    "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "indicators": ["Specific security indicators found"]
}},
"narrative_markdown": "## Executive Summary\\n\\n[2-3 sentences summarizing key findings]\\n\\n### Technical Analysis\\n\\n**Error Distribution:**\\n- ERROR: X entries (X%)\\n- WARN: X entries (X%)\\n- INFO: X entries (X%)\\n\\n**Affected Components:**\\n1. **[ComponentName]**: X errors - [brief description]\\n\\n**Root Cause Analysis:**\\n[Specific technical explanation based on log patterns]\\n\\n**Recommended Actions:**\\n1. [Action 1]\\n2. [Action 2]\\n\\n### Evidence\\n```\\n[Key log lines supporting findings]\\n```\\n\\n**Analysis Confidence:** X%"
}}

LOGS TO ANALYZE (analyze every line):
{{logs[:8000]}}

User Context: {{instruction}}

OUTPUT: Valid JSON only. No conversational text. No questions. Just the analysis report."""
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
        prompt = f"""You are a helpful IT support AI assisting with log analysis.

You MUST format every response using markdown with this structure:
## Summary
Brief overview of your answer.
## Details
- Use bullet points for key items
- **Bold** important terms
- Reference actual log patterns when available
## Recommendations
1. Numbered action steps if applicable

Never output plain paragraph blocks or unstructured essay text.
Always be concise and reference log evidence when available.

{history_str}
User Question: {question}"""
        res = self._route(prompt)
        return {"status": res["status"], "answer": res.get("text", "")}

def get_llm_router():
    return LLMRouter()
