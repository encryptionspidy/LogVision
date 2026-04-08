import React from 'react';
import { Message } from '../types';
import MarkdownRenderer from './MarkdownRenderer';
import { User, Bot } from 'lucide-react';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  
  return (
    <div className={`chat-message ${isUser ? 'ml-auto' : 'mr-auto'}`}>
      <div className={`message-container ${isUser ? 'user-message' : 'assistant-message'}`}>
        <div className="flex items-start space-x-3">
          <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
            isUser ? 'bg-blue-500' : 'bg-gray-600'
          }`}>
            {isUser ? (
              <User className="w-4 h-4 text-white" />
            ) : (
              <Bot className="w-4 h-4 text-white" />
            )}
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium mb-1">
              {isUser ? 'You' : 'LogVision AI'}
            </div>
            
            <div className="text-sm text-gray-500 mb-2">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
            
            <MarkdownRenderer content={message.content} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
