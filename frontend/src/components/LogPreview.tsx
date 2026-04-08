import React, { useState, useEffect, useRef } from 'react';
import { Minimize2, Maximize2, Search, FileText, AlertTriangle, Info, Filter, X } from 'lucide-react';

interface LogPreviewProps {
  logs: string;
  isVisible: boolean;
  onToggleVisibility: () => void;
}

const LogPreview: React.FC<LogPreviewProps> = ({ logs, isVisible, onToggleVisibility }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterLevel, setFilterLevel] = useState<'all' | 'errors' | 'warnings' | 'info'>('all');
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<HTMLDivElement>(null);
  const startPos = useRef({ x: 0, y: 0 });

  if (!logs || !isVisible) return null;

  // Smart positioning - avoid chat area
  useEffect(() => {
    const updatePosition = () => {
      const chatArea = document.querySelector('[class*="chat"]');
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      
      let x = viewportWidth - 420; // Default right position
      let y = viewportHeight - 300; // Default bottom position
      
      // Adjust if overlapping with chat
      if (chatArea) {
        const rect = chatArea.getBoundingClientRect();
        if (x < rect.right && x + 400 > rect.left) {
          x = rect.left - 420; // Move to left of chat
        }
      }
      
      setPosition({ x: Math.max(10, x), y: Math.max(10, y) });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    return () => window.removeEventListener('resize', updatePosition);
  }, []);

  // Drag functionality
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    startPos.current = { x: e.clientX - position.x, y: e.clientY - position.y };
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setPosition({
          x: e.clientX - startPos.current.x,
          y: e.clientY - startPos.current.y
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // Intelligent log filtering
  const filterLogs = (lines: string[]) => {
    let filtered = lines;
    
    if (searchTerm) {
      filtered = filtered.filter(line => 
        line.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (filterLevel !== 'all') {
      filtered = filtered.filter(line => {
        const lowerLine = line.toLowerCase();
        switch (filterLevel) {
          case 'errors':
            return lowerLine.includes('error') || lowerLine.includes('exception') || lowerLine.includes('failed');
          case 'warnings':
            return lowerLine.includes('warning') || lowerLine.includes('warn');
          case 'info':
            return lowerLine.includes('info') || lowerLine.includes('debug');
          default:
            return true;
        }
      });
    }
    
    return filtered;
  };

  const allLines = logs.split('\n');
  const filteredLogs = filterLogs(allLines);
  const displayLogs = isExpanded ? filteredLogs : filteredLogs.slice(0, 8);
  
  // Smart excerpt detection
  const getRelevantExcerpts = () => {
    const errorLines = allLines.filter(line => 
      line.toLowerCase().includes('error') || 
      line.toLowerCase().includes('exception') || 
      line.toLowerCase().includes('failed')
    );
    
    if (errorLines.length > 0) {
      return errorLines.slice(0, 3);
    }
    
    // Get first few lines if no errors
    return allLines.slice(0, 3);
  };

  const relevantExcerpts = getRelevantExcerpts();

  return (
    <div
      ref={dragRef}
      className="fixed bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-w-md"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        width: isExpanded ? '400px' : '320px',
        maxHeight: isExpanded ? '500px' : '300px',
        transition: isDragging ? 'none' : 'all 0.2s ease-in-out'
      }}
    >
      {/* Header */}
      <div 
        className="flex items-center justify-between p-3 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 rounded-t-lg cursor-move"
        onMouseDown={handleMouseDown}
      >
        <div className="flex items-center space-x-2">
          <FileText className="w-4 h-4 text-gray-600" />
          <span className="text-sm font-medium text-gray-700">Log Preview</span>
          <div className="flex items-center space-x-1">
            {filterLevel === 'errors' && <AlertTriangle className="w-3 h-3 text-red-500" />}
            {filterLevel === 'warnings' && <AlertTriangle className="w-3 h-3 text-yellow-500" />}
            {filterLevel === 'info' && <Info className="w-3 h-3 text-blue-500" />}
            <span className="text-xs text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded">
              {filteredLogs.length}/{allLines.length}
            </span>
          </div>
        </div>
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title={isExpanded ? "Minimize" : "Expand"}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button
            onClick={onToggleVisibility}
            className="p-1 text-gray-400 hover:text-red-600 transition-colors"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Quick Excerpts (when minimized) */}
      {!isExpanded && relevantExcerpts.length > 0 && (
        <div className="p-2 border-b border-gray-200 bg-red-50">
          <div className="text-xs font-medium text-red-800 mb-1 flex items-center">
            <AlertTriangle className="w-3 h-3 mr-1" />
            Key Issues
          </div>
          {relevantExcerpts.map((line, index) => (
            <div key={index} className="text-xs font-mono text-red-700 py-0.5 truncate hover:bg-red-100 cursor-pointer">
              {line}
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="p-2 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-2 mb-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-3 h-3 text-gray-400" />
            <input
              type="text"
              placeholder="Search logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-7 pr-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value as any)}
            className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="errors">Errors</option>
            <option value="warnings">Warnings</option>
            <option value="info">Info</option>
          </select>
        </div>
        
        {/* Filter Pills */}
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setFilterLevel('all')}
            className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
              filterLevel === 'all' 
                ? 'bg-blue-100 text-blue-700' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            All ({allLines.length})
          </button>
          <button
            onClick={() => setFilterLevel('errors')}
            className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
              filterLevel === 'errors' 
                ? 'bg-red-100 text-red-700' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Errors ({allLines.filter(l => l.toLowerCase().includes('error')).length})
          </button>
          <button
            onClick={() => setFilterLevel('warnings')}
            className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
              filterLevel === 'warnings' 
                ? 'bg-yellow-100 text-yellow-700' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Warnings ({allLines.filter(l => l.toLowerCase().includes('warning')).length})
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="overflow-y-auto" style={{ maxHeight: isExpanded ? '350px' : '150px' }}>
        <div className="p-2">
          {displayLogs.length > 0 ? (
            displayLogs.map((line, index) => {
              const isError = line.toLowerCase().includes('error') || line.toLowerCase().includes('exception');
              const isWarning = line.toLowerCase().includes('warning') || line.toLowerCase().includes('warn');
              
              return (
                <div 
                  key={index} 
                  className={`text-xs font-mono py-0.5 hover:bg-gray-50 break-all cursor-pointer transition-colors ${
                    isError ? 'text-red-700 bg-red-50' : 
                    isWarning ? 'text-yellow-700 bg-yellow-50' : 
                    'text-gray-700'
                  }`}
                  title={line}
                >
                  {line || <span className="text-gray-400">&nbsp;</span>}
                </div>
              );
            })
          ) : (
            <div className="text-center text-gray-500 py-4">
              <Filter className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-xs">No logs match current filters</p>
            </div>
          )}
          
          {!isExpanded && filteredLogs.length > 8 && (
            <button
              onClick={() => setIsExpanded(true)}
              className="text-xs text-blue-600 hover:text-blue-700 mt-2 w-full text-center py-1 bg-blue-50 rounded hover:bg-blue-100 transition-colors"
            >
              Show {filteredLogs.length - 8} more lines...
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default LogPreview;
