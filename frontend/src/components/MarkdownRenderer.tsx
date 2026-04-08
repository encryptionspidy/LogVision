import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // Could add toast notification here
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const components = {
    // Custom code block rendering
    code: ({ node, inline, className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';
      
      if (!inline && children) {
        const codeContent = String(children).replace(/\n$/, '');
        const isCommand = className?.includes('bash') || 
                         codeContent.includes('lsof') || 
                         codeContent.includes('kill') ||
                         codeContent.includes('systemctl') ||
                         codeContent.includes('docker') ||
                         codeContent.includes('ping') ||
                         codeContent.includes('curl');
        
        return (
          <div className={`${isCommand ? 'command-block' : 'code-block'} relative group`}>
            <button
              onClick={() => copyToClipboard(codeContent)}
              className="copy-button"
              title="Copy to clipboard"
            >
              Copy
            </button>
            <SyntaxHighlighter
              style={vscDarkPlus}
              language={language || 'bash'}
              PreTag="pre"
              {...props}
            >
              {codeContent}
            </SyntaxHighlighter>
          </div>
        );
      }
      
      // Inline code
      return (
        <code className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
          {children}
        </code>
      );
    },
    
    // Enhanced blockquote for log evidence
    blockquote: ({ children, ...props }: any) => {
      const content = String(children).toLowerCase();
      const isLogEvidence = content.includes('error') || 
                           content.includes('failed') || 
                           content.includes('exception') ||
                           content.includes('critical');
      
      if (isLogEvidence) {
        return (
          <div className="log-evidence" {...props}>
            {children}
          </div>
        );
      }
      
      return (
        <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-600" {...props}>
          {children}
        </blockquote>
      );
    },
    
    // Custom headings
    h1: ({ children, ...props }: any) => (
      <h1 className="text-2xl font-bold text-gray-900 mb-4 mt-6" {...props}>
        {children}
      </h1>
    ),
    
    h2: ({ children, ...props }: any) => (
      <h2 className="text-xl font-semibold text-gray-900 mb-3 mt-5" {...props}>
        {children}
      </h2>
    ),
    
    h3: ({ children, ...props }: any) => (
      <h3 className="text-lg font-medium text-gray-900 mb-2 mt-4" {...props}>
        {children}
      </h3>
    ),
    
    // Custom paragraphs
    p: ({ children, ...props }: any) => (
      <p className="text-gray-700 leading-relaxed mb-4" {...props}>
        {children}
      </p>
    ),
    
    // Custom lists
    ul: ({ children, ...props }: any) => (
      <ul className="space-y-2 mb-4 list-disc list-inside" {...props}>
        {children}
      </ul>
    ),
    
    ol: ({ children, ...props }: any) => (
      <ol className="space-y-2 mb-4 list-decimal list-inside" {...props}>
        {children}
      </ol>
    ),
    
    li: ({ children, ...props }: any) => (
      <li className="text-gray-700" {...props}>
        {children}
      </li>
    ),
    
    // Custom strong/bold
    strong: ({ children, ...props }: any) => (
      <strong className="font-semibold text-gray-900" {...props}>
        {children}
      </strong>
    ),
    
    // Custom emphasis/italic
    em: ({ children, ...props }: any) => (
      <em className="italic text-gray-700" {...props}>
        {children}
      </em>
    ),
  };

  return (
    <div className={`prose-custom ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;
