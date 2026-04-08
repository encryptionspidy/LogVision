export interface AnalysisSession {
  id: string;
  summary: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN';
  created_at: string;
  metadata: SessionMetadata;
  messages: Message[];
}

export interface SessionMetadata {
  status: string;
  metrics: LogMetrics;
  insights: Insight[];
  root_causes: RootCause[];
  evidence: Evidence[];
  fixes: Fixes;
  security_analysis: SecurityAnalysis;
  patterns: Pattern[];
  confidence: number;
  quality_metrics: QualityMetrics;
  actionable_commands: number;
  evidence_count: number;
  insight_count: number;
  has_security_issues: boolean;
  user_intent: string;
}

export interface LogMetrics {
  total_logs: number;
  error_rate: number;
  unique_ips: number;
  time_span: string;
  affected_services: string[];
}

export interface Insight {
  title: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  evidence: string[];
}

export interface RootCause {
  issue: string;
  evidence: string[];
  impact: string;
  recommendation: string;
}

export interface Evidence {
  log_line: string;
  line_number: number;
  significance: string;
}

export interface Fixes {
  commands: Command[];
  config_changes: ConfigChange[];
}

export interface Command {
  purpose: string;
  command: string;
  explanation: string;
}

export interface ConfigChange {
  file: string;
  change: string;
  reason: string;
}

export interface SecurityAnalysis {
  threat_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  indicators: string[];
  recommendations: string[];
}

export interface Pattern {
  type: string;
  description: string;
  count: number;
  timeframe: string;
}

export interface QualityMetrics {
  evidence_score: number;
  specificity_score: number;
  actionability_score: number;
  overall_score: number;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface AnalysisRequest {
  log_text: string;
  instruction?: string;
  question?: string;
  features?: string[];
}

export interface AnalysisResponse {
  analysis_id: string;
  status: string;
  risk_level: string;
  actionable_items: number;
  evidence_count: number;
}

export interface ChatRequest {
  question: string;
}
