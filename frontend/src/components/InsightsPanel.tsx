import React from 'react';
import { SessionMetadata } from '../types';
import { AlertTriangle, Shield, Target, TrendingUp, CheckCircle } from 'lucide-react';

interface InsightsPanelProps {
  metadata?: any;
  riskLevel?: string;
}

const InsightsPanel: React.FC<InsightsPanelProps> = ({ metadata, riskLevel }) => {
  const getRiskColor = (level: string) => {
    switch (level) {
      case 'CRITICAL': return 'text-red-600 bg-red-50 border-red-200';
      case 'HIGH': return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'MEDIUM': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'LOW': return 'text-green-600 bg-green-50 border-green-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getQualityColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
        <Target className="w-5 h-5 mr-2 text-blue-600" />
        Analysis Insights
      </h3>
      
      {/* Risk Level */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Risk Level</span>
          <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getRiskColor(riskLevel || 'UNKNOWN')}`}>
            {riskLevel || 'UNKNOWN'}
          </span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-blue-600">{metadata.insight_count}</div>
          <div className="text-xs text-gray-600">Insights</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-green-600">{metadata.actionable_commands}</div>
          <div className="text-xs text-gray-600">Actionable Commands</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-purple-600">{metadata.evidence_count}</div>
          <div className="text-xs text-gray-600">Evidence Items</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-orange-600">{metadata.patterns.length}</div>
          <div className="text-xs text-gray-600">Patterns</div>
        </div>
      </div>

      {/* Quality Metrics */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Response Quality</h4>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600">Overall Score</span>
            <span className={`text-sm font-medium ${getQualityColor(metadata.quality_metrics.overall_score)}`}>
              {metadata.quality_metrics.overall_score}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${metadata.quality_metrics.overall_score}%` }}
            />
          </div>
          
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-gray-600">Evidence</span>
            <span className={`text-xs font-medium ${getQualityColor(metadata.quality_metrics.evidence_score)}`}>
              {metadata.quality_metrics.evidence_score}%
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600">Specificity</span>
            <span className={`text-xs font-medium ${getQualityColor(metadata.quality_metrics.specificity_score)}`}>
              {metadata.quality_metrics.specificity_score}%
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600">Actionability</span>
            <span className={`text-xs font-medium ${getQualityColor(metadata.quality_metrics.actionability_score)}`}>
              {metadata.quality_metrics.actionability_score}%
            </span>
          </div>
        </div>
      </div>

      {/* Analysis Confidence */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Analysis Confidence</span>
          <span className={`text-sm font-medium ${getConfidenceColor(metadata.confidence)}`}>
            {metadata.confidence}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all duration-300 ${
              metadata.confidence >= 80 ? 'bg-green-600' : 
              metadata.confidence >= 60 ? 'bg-yellow-600' : 'bg-red-600'
            }`}
            style={{ width: `${metadata.confidence}%` }}
          />
        </div>
      </div>

      {/* Security Status */}
      {metadata.has_security_issues && (
        <div className="mb-6">
          <div className="flex items-center p-3 bg-red-50 border border-red-200 rounded-lg">
            <Shield className="w-5 h-5 text-red-600 mr-2" />
            <div>
              <div className="text-sm font-medium text-red-900">Security Issues Detected</div>
              <div className="text-xs text-red-700">
                {metadata.security_analysis.indicators.length} indicators found
              </div>
            </div>
          </div>
        </div>
      )}

      {/* User Intent */}
      <div className="text-xs text-gray-500 text-center">
        Analysis type: <span className="font-medium">{metadata.user_intent}</span>
      </div>
    </div>
  );
};

export default InsightsPanel;
