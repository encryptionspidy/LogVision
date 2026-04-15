"""
Structured signal extraction from logs.

Extracts meaningful patterns and signals from logs before LLM processing
to enable context reuse and reduce token usage.
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class SignalExtractor:
    """
    Extract structured signals from logs for context reuse.
    
    Extracts:
    - Component/service mapping
    - Error pattern clusters
    - Severity distribution
    - Timeline data points
    - Repeating log signatures
    """
    
    # Patterns for extracting components
    COMPONENT_PATTERNS = [
        r'\[(\w+)\]',  # [ServiceName]
        r'(\w+)\s*:',  # ServiceName:
        r'<(\w+)>',    # <ServiceName>
    ]
    
    # Severity level patterns
    SEVERITY_PATTERNS = {
        'CRITICAL': r'\b(CRITICAL|FATAL|EMERGENCY)\b',
        'ERROR': r'\b(ERROR|ERR)\b',
        'WARN': r'\b(WARN|WARNING)\b',
        'INFO': r'\b(INFO)\b',
        'DEBUG': r'\b(DEBUG|DBG)\b',
    }
    
    # Error signature patterns
    ERROR_SIGNATURE_PATTERNS = [
        r'exception', r'error', r'failed', r'timeout',
        r'denied', r'refused', r'unable', r'cannot'
    ]
    
    def __init__(self):
        """Initialize the signal extractor."""
        self.component_pattern = re.compile('|'.join(self.COMPONENT_PATTERNS))
    
    def extract_signals(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        Extract all structured signals from log lines.
        
        Args:
            log_lines: List of log lines
            
        Returns:
            Dictionary containing extracted signals
        """
        signals = {
            'components': self._extract_components(log_lines),
            'severity_distribution': self._extract_severity_distribution(log_lines),
            'error_patterns': self._extract_error_patterns(log_lines),
            'timeline_data': self._extract_timeline_data(log_lines),
            'repeating_signatures': self._extract_repeating_signatures(log_lines),
            'total_lines': len(log_lines)
        }
        
        logger.info(f"Extracted signals from {len(log_lines)} lines: "
                   f"{len(signals['components'])} components, "
                   f"{sum(signals['severity_distribution'].values())} severity events")
        
        return signals
    
    def _extract_components(self, log_lines: List[str]) -> List[Dict[str, Any]]:
        """
        Extract component/service information from logs.
        
        Returns list of components with error counts.
        """
        component_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'error_count': 0,
            'warn_count': 0
        })
        
        for line in log_lines:
            # Try to extract component name
            component = None
            for pattern in self.COMPONENT_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    component = match.group(1)
                    break
            
            if component:
                component_stats[component]['count'] += 1
                
                # Count errors and warnings
                line_upper = line.upper()
                if any(kw in line_upper for kw in ['ERROR', 'FATAL', 'CRITICAL']):
                    component_stats[component]['error_count'] += 1
                elif any(kw in line_upper for kw in ['WARN', 'WARNING']):
                    component_stats[component]['warn_count'] += 1
        
        # Convert to list and sort by total count
        components = []
        for name, stats in component_stats.items():
            if stats['count'] > 0:  # Only include components that appear
                components.append({
                    'name': name,
                    'count': stats['count'],
                    'error_count': stats['error_count'],
                    'warn_count': stats['warn_count'],
                    'severity': 'HIGH' if stats['error_count'] > 5 else 'MEDIUM' if stats['error_count'] > 0 else 'LOW'
                })
        
        # Sort by error count, then total count
        components.sort(key=lambda x: (x['error_count'], x['count']), reverse=True)
        
        return components[:20]  # Return top 20 components
    
    def _extract_severity_distribution(self, log_lines: List[str]) -> Dict[str, int]:
        """
        Extract severity distribution from logs.
        
        Returns count of each severity level.
        """
        distribution = {
            'CRITICAL': 0,
            'ERROR': 0,
            'WARN': 0,
            'INFO': 0,
            'DEBUG': 0,
            'UNKNOWN': 0
        }
        
        for line in log_lines:
            line_upper = line.upper()
            matched = False
            
            for severity, pattern in self.SEVERITY_PATTERNS.items():
                if re.search(pattern, line_upper):
                    distribution[severity] += 1
                    matched = True
                    break
            
            if not matched:
                distribution['UNKNOWN'] += 1
        
        return distribution
    
    def _extract_error_patterns(self, log_lines: List[str]) -> List[Dict[str, Any]]:
        """
        Extract error patterns and their frequencies.
        
        Returns list of error patterns with counts.
        """
        error_lines = []
        
        for line in log_lines:
            line_upper = line.upper()
            if any(kw in line_upper for kw in self.ERROR_SIGNATURE_PATTERNS):
                error_lines.append(line)
        
        # Create simple signatures by removing variable parts
        signatures = []
        for line in error_lines:
            # Remove numbers, timestamps, and IPs
            signature = re.sub(r'\d+', 'N', line)
            signature = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP', signature)
            signature = re.sub(r'\b[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}\b', 'UUID', signature)
            signatures.append(signature)
        
        # Count signature frequencies
        signature_counts = Counter(signatures)
        
        # Convert to list
        patterns = []
        for signature, count in signature_counts.most_common(20):
            patterns.append({
                'signature': signature[:100],  # Truncate long signatures
                'count': count,
                'severity': 'HIGH' if count > 5 else 'MEDIUM' if count > 2 else 'LOW'
            })
        
        return patterns
    
    def _extract_timeline_data(self, log_lines: List[str]) -> List[Dict[str, Any]]:
        """
        Extract timeline data points from logs.
        
        Returns list of time buckets with error counts.
        """
        # Try to extract timestamps
        timestamp_patterns = [
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',  # 2024-03-27 10:15:32
            r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})',  # 03/27/2024 10:15:32
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',  # Mar 27 10:15:32
        ]
        
        time_points = []
        
        for line in log_lines:
            timestamp = None
            for pattern in timestamp_patterns:
                match = re.search(pattern, line)
                if match:
                    timestamp = match.group(1)
                    break
            
            if timestamp:
                # Check if line has error
                line_upper = line.upper()
                has_error = any(kw in line_upper for kw in ['ERROR', 'FATAL', 'CRITICAL'])
                
                time_points.append({
                    'timestamp': timestamp,
                    'has_error': has_error
                })
        
        # Bucket by minute (simplified)
        time_buckets = defaultdict(lambda: {'count': 0, 'error_count': 0})
        
        for point in time_points:
            # Use first 10 chars of timestamp as bucket key (minute-level)
            bucket_key = point['timestamp'][:10] if len(point['timestamp']) >= 10 else point['timestamp']
            time_buckets[bucket_key]['count'] += 1
            if point['has_error']:
                time_buckets[bucket_key]['error_count'] += 1
        
        # Convert to list
        timeline = []
        for bucket_key, stats in sorted(time_buckets.items()):
            timeline.append({
                'time': bucket_key,
                'total_count': stats['count'],
                'error_count': stats['error_count'],
                'error_rate': stats['error_count'] / stats['count'] if stats['count'] > 0 else 0
            })
        
        return timeline[:50]  # Return up to 50 time buckets
    
    def _extract_repeating_signatures(self, log_lines: List[str]) -> List[Dict[str, Any]]:
        """
        Extract repeating log signatures.
        
        Returns list of signatures that repeat frequently.
        """
        # Create signatures by normalizing variable parts
        signatures = []
        for line in log_lines:
            # Normalize: remove numbers, timestamps, UUIDs, IPs
            signature = re.sub(r'\d+', 'N', line)
            signature = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP', signature)
            signature = re.sub(r'\b[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}\b', 'UUID', signature)
            signature = re.sub(r'\b0x[0-9a-fA-F]+\b', 'HEX', signature)
            signature = signature.strip()
            if signature:
                signatures.append(signature)
        
        # Count frequencies
        signature_counts = Counter(signatures)
        
        # Return top repeating signatures
        repeating = []
        for signature, count in signature_counts.most_common(15):
            if count > 2:  # Only include signatures that repeat
                repeating.append({
                    'signature': signature[:80],  # Truncate
                    'count': count,
                    'percentage': round(count / len(log_lines) * 100, 2)
                })
        
        return repeating
    
    def extract_key_log_snippets(self, log_lines: List[str], count: int = 10) -> List[str]:
        """
        Extract key log snippets for evidence.
        
        Prioritizes:
        - Error lines
        - Lines with priority keywords
        - Lines from high-error components
        
        Args:
            log_lines: List of log lines
            count: Number of snippets to extract
            
        Returns:
            List of log snippets
        """
        scored_lines = []
        
        for i, line in enumerate(log_lines):
            score = 0
            line_upper = line.upper()
            
            # Score based on severity
            if 'CRITICAL' in line_upper or 'FATAL' in line_upper:
                score += 10
            elif 'ERROR' in line_upper:
                score += 7
            elif 'WARN' in line_upper or 'WARNING' in line_upper:
                score += 5
            
            # Score based on priority keywords
            for keyword in ['exception', 'timeout', 'failed', 'denied', 'refused']:
                if keyword in line_upper:
                    score += 3
            
            # Score based on length (prefer meaningful logs)
            if len(line) > 50 and len(line) < 500:
                score += 1
            
            scored_lines.append((score, i, line))
        
        # Sort by score and return top snippets
        scored_lines.sort(key=lambda x: x[0], reverse=True)
        
        snippets = []
        for score, idx, line in scored_lines[:count]:
            snippets.append(line.strip())
        
        return snippets
