import React, { useState } from 'react';
import { Upload, FileText, Send } from 'lucide-react';

interface LogInputProps {
  onSubmit: (data: { log_text: string; instruction?: string; question?: string }) => void;
  isLoading?: boolean;
}

const LogInput: React.FC<LogInputProps> = ({ onSubmit, isLoading = false }) => {
  const [logText, setLogText] = useState('');
  const [instruction, setInstruction] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setLogText(text);
      };
      reader.readAsText(file);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setLogText(text);
      };
      reader.readAsText(file);
    }
  };

  const handleSubmit = () => {
    if (!logText.trim()) return;
    
    onSubmit({
      log_text: logText,
      instruction: instruction || undefined,
    });
    
    // Clear form after submission
    setLogText('');
    setInstruction('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
        <FileText className="w-5 h-5 mr-2 text-blue-600" />
        Log Analysis
      </h3>

      {/* File Upload / Drag & Drop */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
        <p className="text-sm text-gray-600 mb-2">
          Drag and drop log files here, or click to browse
        </p>
        <input
          type="file"
          accept=".log,.txt"
          onChange={handleFileUpload}
          className="hidden"
          id="file-upload"
        />
        <label
          htmlFor="file-upload"
          className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 cursor-pointer"
        >
          Choose File
        </label>
      </div>

      {/* Log Text Input */}
      <div className="mt-4">
        <label htmlFor="log-text" className="block text-sm font-medium text-gray-700 mb-2">
          Log Content
        </label>
        <textarea
          id="log-text"
          value={logText}
          onChange={(e) => setLogText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Paste your log content here or upload a file above..."
          className="w-full h-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
        />
      </div>

      {/* Instruction Input */}
      <div className="mt-4">
        <label htmlFor="instruction" className="block text-sm font-medium text-gray-700 mb-2">
          Analysis Focus (Optional)
        </label>
        <input
          type="text"
          id="instruction"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="e.g., 'find security issues', 'fix errors', 'analyze anomalies'..."
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Submit Button */}
      <div className="mt-4 flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={!logText.trim() || isLoading}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Analyzing...
            </>
          ) : (
            <>
              <Send className="w-4 h-4 mr-2" />
              Analyze Logs
            </>
          )}
        </button>
      </div>

      {/* Quick Actions */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 mb-2">Quick actions:</p>
        <div className="flex flex-wrap gap-2">
          {[
            'find anomalies',
            'fix errors',
            'security issues',
            'performance problems',
            'connection issues'
          ].map((action) => (
            <button
              key={action}
              onClick={() => setInstruction(action)}
              className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
            >
              {action}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default LogInput;
