import React from 'react';
import { History, MessageSquare, Clock, AlertTriangle, Edit2, Trash2 } from 'lucide-react';

interface HistoryItem {
  id: string;
  summary: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN';
  created_at: string;
  messages?: Array<{ role: string; content: string }>;
}

interface ChatHistoryProps {
  sessions: HistoryItem[];
  currentSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newName: string) => void;
}

const ChatHistory: React.FC<ChatHistoryProps> = ({
  sessions,
  currentSessionId,
  onSelectSession,
  onDeleteSession,
  onRenameSession
}) => {
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editName, setEditName] = React.useState('');

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'CRITICAL': return 'bg-red-100 text-red-800';
      case 'HIGH': return 'bg-orange-100 text-orange-800';
      case 'MEDIUM': return 'bg-yellow-100 text-yellow-800';
      case 'LOW': return 'bg-green-100 text-green-800';
      case 'UNKNOWN': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffHours < 48) return 'Yesterday';
    return date.toLocaleDateString();
  };

  const handleRename = (sessionId: string, currentName: string) => {
    setEditingId(sessionId);
    setEditName(currentName);
  };

  const saveRename = (sessionId: string) => {
    if (editName.trim()) {
      onRenameSession(sessionId, editName.trim());
      setEditingId(null);
      setEditName('');
    }
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditName('');
  };

  const handleDelete = (sessionId: string, summary: string) => {
    if (window.confirm(`Are you sure you want to delete "${summary}"? This action cannot be undone.`)) {
      onDeleteSession(sessionId);
    }
  };

  return (
    <div className="space-y-2">
      {sessions.map((session) => (
        <div
          key={session.id}
          className={`p-3 rounded-lg border transition-all ${
            currentSessionId === session.id
              ? 'bg-blue-50 border-blue-200'
              : 'bg-white border-gray-200 hover:bg-gray-50'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0 mr-2">
              {editingId === session.id ? (
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onBlur={() => saveRename(session.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      saveRename(session.id);
                    } else if (e.key === 'Escape') {
                      cancelRename();
                    }
                  }}
                  className="w-full px-2 py-1 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              ) : (
                <div onClick={() => handleRename(session.id, session.summary)}>
                  <h3 className="text-sm font-medium text-gray-900 truncate cursor-pointer hover:text-blue-600">
                    {session.summary || 'Untitled Analysis'}
                  </h3>
                </div>
              )}
              
              <div className="flex items-center space-x-2 mt-1">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-xs text-gray-500">{formatTime(session.created_at)}</span>
              </div>
              
              <div className="flex items-center space-x-2 mt-1">
                <MessageSquare className="w-3 h-3 text-gray-400" />
                <span className="text-xs text-gray-500">{session.messages?.length || 0} messages</span>
              </div>
            </div>
            
            <div className="flex items-center space-x-1">
              <span className={`text-xs px-2 py-1 rounded-full ${getRiskColor(session.risk_level)}`}>
                {session.risk_level}
              </span>
              
              <div className="flex space-x-1">
                {editingId === session.id ? (
                  <>
                    <button
                      onClick={() => saveRename(session.id)}
                      className="p-1 text-green-600 hover:text-green-700 transition-colors"
                      title="Save"
                    >
                      ✓
                    </button>
                    <button
                      onClick={cancelRename}
                      className="p-1 text-gray-600 hover:text-gray-700 transition-colors"
                      title="Cancel"
                    >
                      ✕
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleRename(session.id, session.summary)}
                      className="p-1 text-blue-600 hover:text-blue-700 transition-colors"
                      title="Rename"
                    >
                      <Edit2 className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => handleDelete(session.id, session.summary)}
                      className="p-1 text-red-600 hover:text-red-700 transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
      
      {sessions.length === 0 && (
        <div className="text-center py-8">
          <History className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          <p className="text-sm text-gray-500">No analysis history yet</p>
          <p className="text-xs text-gray-400 mt-1">Start analyzing logs to see your history</p>
        </div>
      )}
    </div>
  );
};

export default ChatHistory;
