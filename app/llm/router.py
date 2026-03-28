import os
from dotenv import load_dotenv

from google import genai
from groq import Groq

# Load environment variables from .env file
load_dotenv()

class LLMRouter:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        
        if not self.gemini_key and not self.groq_key:
            raise Exception("No API keys configured")

        if self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
        if self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)

    def _call_gemini(self, prompt):
        # Use a highly capable Gemini model
        response = self.gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        return response.text

    def _call_groq(self, prompt):
        # Use a highly capable open model on Groq
        chat_completion = self.groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        return chat_completion.choices[0].message.content

    def _route(self, prompt):
        error_msgs = []
        if self.gemini_key:
            try:
                text = self._call_gemini(prompt)
                return {"status": "success", "text": text}
            except Exception as e:
                error_msgs.append(f"Gemini error: {e}")
        
        if self.groq_key:
            try:
                text = self._call_groq(prompt)
                return {"status": "success", "text": text}
            except Exception as e:
                error_msgs.append(f"Groq error: {e}")
                
        raise Exception(" | ".join(error_msgs) if error_msgs else "No API keys configured")
        
    def generate_analysis(self, payload_context, instruction="", *args, **kwargs):
        import json
        import re

        if isinstance(payload_context, str):
            logs = payload_context
            parsed_context = {"raw_logs_snippet": logs[:5000]}
        else:
            logs = payload_context.get("raw_logs", "")
            parsed_context = payload_context

        # Step 6: Hardcoded heuristics
        heuristics_found = []
        if re.search(r"Address already in use", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "Address already in use", "inference": "port conflict"})
        if re.search(r"timeout", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "timeout", "inference": "network latency issue"})
        if re.search(r"permission denied", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "permission denied", "inference": "access control problem"})
        if re.search(r"connection refused", logs, re.IGNORECASE):
            heuristics_found.append({"pattern": "connection refused", "inference": "service offline"})

        # Step 1: Provide structured context
        context_to_llm = {
            "heuristics_found": heuristics_found,
            "instruction": instruction,
            "selected_features": parsed_context.get("features", []),
            "parsed_statistics": parsed_context.get("stats", {}),
            "anomalies": parsed_context.get("anomalies", [])[:20],
            "severity_scores": parsed_context.get("severity_distribution", {}),
            "raw_logs_snippet": logs[:5000]
        }
        
        prompt = f"""You are a log analysis engine.
Your job is to analyze structured log data and produce factual insights.
Never provide generic cybersecurity essays.
Only use information present in logs.
If evidence is insufficient, say so clearly.
Focus on patterns, anomalies, errors, repeated messages, timestamps.
Output JSON only. Do not wrap in markdown code blocks, just raw JSON.

If user selects features like "anomaly detection", prioritize anomalies section. 
If user selects "infographics", ensure 'charts' arrays are robustly populated.

REQUIRED OUTPUT STRUCTURE:
{{
"summary": "...",
"risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
"confidence": 0-100,
"key_findings": [
{{
"title": "...",
"description": "...",
"severity": "...",
"confidence": 0-100
}}
],
"anomalies": [
{{
"pattern": "...",
"count": 0,
"severity": "...",
"example_log": "..."
}}
],
"root_causes": [
{{
"issue": "...",
"evidence": "...",
"recommendation": "..."
}}
],
"metrics": {{
"total_logs": 0,
"error_rate": 0,
"unique_ips": 0,
"time_span": "..."
}},
"charts": {{
"severity_distribution": [
{{"level":"INFO","count":0}}
],
"timeline": [
{{"time":"00:00","errors":0}}
],
"top_patterns": [
{{"pattern":"...","count":0}}
]
}},
"chat_response": "Formatted markdown explanation. You MUST use markdown headings and structure. Use exactly this format:\n## Summary\nShort explanation of overall findings referencing actual log patterns.\n## Key Issues\n- **issue title** — short explanation with log evidence\n## Root Cause\nClear explanation referencing specific log entries.\n## Recommendations\n1. Action step\n2. Action step\n## Confidence\nNN% — brief justification based on log completeness.\n\nNever output plain paragraph blocks. Never output generic cybersecurity essays. Always reference actual log patterns."
}}

User Context:
{json.dumps(context_to_llm, indent=2)}
"""
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
            parsed = json.loads(text)
            # Ensure chat_response exists and is proper markdown, not JSON
            chat_resp = parsed.get("chat_response", "")
            if not chat_resp or chat_resp.strip().startswith("{"):
                # Generate markdown from structured data if chat_response is missing/invalid
                chat_resp = self._build_markdown_from_parsed(parsed)
                parsed["chat_response"] = chat_resp
            return {"status": "success", "summary": parsed}
        except Exception as e:
            # Fallback: try to extract chat_response via regex from raw text
            chat_match = re.search(r'"chat_response"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if chat_match:
                fallback_md = chat_match.group(1).replace("\\n", "\n").replace('\\"', '"')
            else:
                fallback_md = "## Summary\nAnalysis completed, but structured response could not be parsed.\n\nPlease try again or rephrase your request."
            return {"status": "success", "summary": {
                "summary": fallback_md,
                "chat_response": fallback_md,
                "error": str(e)
            }}

    def _build_markdown_from_parsed(self, data):
        """Build a clean markdown response from parsed JSON when chat_response is missing."""
        parts = []

        summary = data.get("summary", "")
        if summary:
            parts.append(f"## Summary\n{summary}")

        findings = data.get("key_findings", [])
        if findings:
            parts.append("## Key Issues")
            for f in findings:
                title = f.get("title", "Unknown")
                desc = f.get("description", "")
                sev = f.get("severity", "")
                conf = f.get("confidence", "")
                parts.append(f"- **{title}** ({sev}, {conf}% confidence) — {desc}")

        root_causes = data.get("root_causes", [])
        if root_causes:
            parts.append("## Root Cause")
            for rc in root_causes:
                issue = rc.get("issue", "")
                evidence = rc.get("evidence", "")
                rec = rc.get("recommendation", "")
                parts.append(f"{issue}")
                if evidence:
                    parts.append(f"  - **Evidence:** {evidence}")
                if rec:
                    parts.append(f"  - **Fix:** {rec}")

        anomalies = data.get("anomalies", [])
        if anomalies:
            parts.append("## Anomalies Detected")
            for a in anomalies:
                pattern = a.get("pattern", "")
                count = a.get("count", 0)
                sev = a.get("severity", "")
                parts.append(f"- **{pattern}** — {count} occurrences ({sev})")

        metrics = data.get("metrics", {})
        if metrics:
            parts.append("## Metrics")
            total = metrics.get("total_logs", "N/A")
            err_rate = metrics.get("error_rate", "N/A")
            if isinstance(err_rate, (int, float)):
                err_rate = f"{err_rate * 100:.1f}%"
            time_span = metrics.get("time_span", "N/A")
            parts.append(f"- **Total logs:** {total}")
            parts.append(f"- **Error rate:** {err_rate}")
            parts.append(f"- **Time span:** {time_span}")

        confidence = data.get("confidence", "")
        risk = data.get("risk_level", "")
        if confidence or risk:
            parts.append("## Confidence")
            if confidence:
                parts.append(f"**{confidence}%** confidence")
            if risk:
                parts.append(f"  — Risk level: **{risk}**")

        return "\n\n".join(parts) if parts else "## Summary\nAnalysis complete."

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
