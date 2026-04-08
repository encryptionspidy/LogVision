import React, { useState, useEffect } from 'react';
import { AnalysisSession, AnalysisRequest, ChatRequest } from './types';
import LogInput from './components/LogInput';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import ChatHistory from './components/ChatHistory';
import LogPreview from './components/LogPreview';
import InsightsPanel from './components/InsightsPanel';
import { MessageSquare, BarChart3, History, Settings, Eye, EyeOff, Zap, TrendingUp } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:5000';

const App: React.FC = () => {
  const [currentSession, setCurrentSession] = useState<AnalysisSession | null>(null);
  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeView, setActiveView] = useState<'chat' | 'insights' | 'history'>('chat');
  const [showLogPreview, setShowLogPreview] = useState(false);
  const [currentLogs, setCurrentLogs] = useState('');
  const [analysisStats, setAnalysisStats] = useState({
    totalAnalyses: 0,
    avgConfidence: 0,
    criticalIssues: 0
  });

  useEffect(() => {
    loadSessions();
    updateStats();
  }, [sessions]);

  const loadSessions = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/analysis/sessions`);
      if (response.ok) {
        const sessionsData = await response.json();
        setSessions(sessionsData);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const updateStats = () => {
    const totalAnalyses = sessions.length;
    const avgConfidence = sessions.length > 0 
      ? Math.round(sessions.reduce((sum, s) => sum + (s.metadata?.confidence || 0), 0) / sessions.length)
      : 0;
    const criticalIssues = sessions.filter(s => s.risk_level === 'CRITICAL').length;
    
    setAnalysisStats({ totalAnalyses, avgConfidence, criticalIssues });
  };

  const startAnalysis = async (data: AnalysisRequest) => {
    setIsLoading(true);
    setCurrentLogs(data.log_text);
    setShowLogPreview(true);
    
    try {
      const response = await fetch(`${API_BASE}/api/analysis/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      const result = await response.json();
      
      // Poll for session completion
      const sessionId = result.analysis_id;
      await pollForCompletion(sessionId);
      
      // Load the completed session
      await loadSession(sessionId);
      
    } catch (error) {
      console.error('Analysis error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const pollForCompletion = async (sessionId: string) => {
    const maxAttempts = 30;
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`${API_BASE}/api/analysis/${sessionId}`);
        if (response.ok) {
          const session = await response.json();
          if (session.metadata?.status === 'complete') {
            return session;
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
      
      await new Promise(resolve => setTimeout(resolve, 1000));
      attempts++;
    }
    
    throw new Error('Analysis timeout');
  };

  const loadSession = async (sessionId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/analysis/${sessionId}`);
      if (response.ok) {
        const session = await response.json();
        setCurrentSession(session);
        setActiveView('chat');
        await loadSessions(); // Refresh sessions list
      }
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  const sendChatMessage = async (message: string) => {
    if (!currentSession) return;

    // Add user message optimistically
    const userMessage = {
      role: 'user' as const,
      content: message,
      timestamp: new Date().toISOString(),
    };

    setCurrentSession(prev => prev ? {
      ...prev,
      messages: [...prev.messages, userMessage]
    } : null);

    try {
      const response = await fetch(`${API_BASE}/api/analysis/${currentSession.id}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: message }),
      });

      if (!response.ok) {
        throw new Error('Chat failed');
      }

      const result = await response.json();
      
      // Add assistant response
      const assistantMessage = {
        role: 'assistant' as const,
        content: result.answer,
        timestamp: new Date().toISOString(),
      };

      setCurrentSession(prev => prev ? {
        ...prev,
        messages: [...prev.messages, assistantMessage]
      } : null);

    } catch (error) {
      console.error('Chat error:', error);
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/analysis/${sessionId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await loadSessions();
        if (currentSession?.id === sessionId) {
          setCurrentSession(null);
          setActiveView('chat');
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const renameSession = async (sessionId: string, newName: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/analysis/${sessionId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ summary: newName }),
      });

      if (response.ok) {
        await loadSessions();
        if (currentSession?.id === sessionId) {
          setCurrentSession(prev => prev ? { ...prev, summary: newName } : null);
        }
      }
    } catch (error) {
      console.error('Failed to rename session:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-2xl font-bold text-gray-900">LogVision</h1>
                <p className="text-sm text-gray-500">AI-powered Log Intelligence Assistant</p>
              </div>
            </div>
            
            {/* Navigation */}
            <nav className="flex space-x-4">
              <button
                onClick={() => setActiveView('chat')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'chat'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <MessageSquare className="w-4 h-4 inline mr-1" />
                Analysis
              </button>
              <button
                onClick={() => setActiveView('insights')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'insights'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <BarChart3 className="w-4 h-4 inline mr-1" />
                Insights
              </button>
              <button
                onClick={() => setActiveView('history')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'history'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <History className="w-4 h-4 inline mr-1" />
                History
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Main Content */}
          <div className="lg:col-span-2">
            {activeView === 'chat' && (
              <>
                {!currentSession ? (
                  <LogInput onSubmit={startAnalysis} isLoading={isLoading} />
                ) : (
                  <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
                    {/* Chat Messages */}
                    <div className="h-96 overflow-y-auto p-4 space-y-4">
                      {currentSession.messages.map((message, index) => (
                        <ChatMessage key={index} message={message} />
                      ))}
                    </div>

                    {/* Chat Input */}
                    <ChatInput
                      onSendMessage={sendChatMessage}
                      disabled={isLoading}
                      placeholder="Ask follow-up questions..."
                    />
                  </div>
                )}
              </>
            )}

            {activeView === 'insights' && currentSession && (
              <InsightsPanel metadata={currentSession.metadata} riskLevel={currentSession.risk_level} />
            )}

            {activeView === 'history' && (
              <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Analysis History</h3>
                  <div className="flex items-center space-x-4 text-sm text-gray-600">
                    <div className="flex items-center">
                      <Zap className="w-4 h-4 mr-1 text-yellow-500" />
                      <span>{analysisStats.totalAnalyses} analyses</span>
                    </div>
                    <div className="flex items-center">
                      <TrendingUp className="w-4 h-4 mr-1 text-green-500" />
                      <span>{analysisStats.avgConfidence}% avg confidence</span>
                    </div>
                  </div>
                </div>
                <ChatHistory
                  sessions={sessions}
                  currentSessionId={currentSession?.id || undefined}
                  onSelectSession={loadSession}
                  onDeleteSession={deleteSession}
                  onRenameSession={renameSession}
                />
              </div>
            )}
          </div>

          {/* Right Column - Session Info */}
          <div className="lg:col-span-1">
            {currentSession && (
              <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Session Details</h3>
                <div className="space-y-3">
                  <div>
                    <div className="text-sm font-medium text-gray-700">Session ID</div>
                    <div className="text-xs text-gray-500 font-mono">{currentSession.id}</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700">Risk Level</div>
                    <div className={`px-2 py-1 text-xs font-medium rounded inline-block ${
                      currentSession.risk_level === 'CRITICAL' ? 'bg-red-100 text-red-800' :
                      currentSession.risk_level === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                      currentSession.risk_level === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-green-100 text-green-800'
                    }`}>
                      {currentSession.risk_level}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700">Messages</div>
                    <div className="text-xs text-gray-500">{currentSession.messages.length} messages</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700">Created</div>
                    <div className="text-xs text-gray-500">
                      {new Date(currentSession.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                {currentSession.metadata && (
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <h4 className="text-sm font-medium text-gray-700 mb-3">Quick Stats</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="text-center p-2 bg-gray-50 rounded">
                        <div className="text-lg font-bold text-blue-600">
                          {currentSession.metadata.insight_count}
                        </div>
                        <div className="text-xs text-gray-600">Insights</div>
                      </div>
                      <div className="text-center p-2 bg-gray-50 rounded">
                        <div className="text-lg font-bold text-green-600">
                          {currentSession.metadata.actionable_commands}
                        </div>
                        <div className="text-xs text-gray-600">Commands</div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="mt-6 flex space-x-2">
                  <button
                    onClick={() => setShowLogPreview(!showLogPreview)}
                    className="flex-1 px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-sm font-medium flex items-center justify-center transition-colors"
                  >
                    {showLogPreview ? <EyeOff className="w-4 h-4 mr-1" /> : <Eye className="w-4 h-4 mr-1" />}
                    {showLogPreview ? 'Hide' : 'Show'} Logs
                  </button>
                  <button
                    onClick={() => {
                      setCurrentSession(null);
                      setActiveView('chat');
                    }}
                    className="flex-1 px-3 py-2 bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 text-sm font-medium transition-colors"
                  >
                    New Analysis
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Log Preview */}
      <LogPreview
        logs={currentLogs}
        isVisible={showLogPreview}
        onToggleVisibility={() => setShowLogPreview(!showLogPreview)}
      />
    </div>
  );
};

export default App;
