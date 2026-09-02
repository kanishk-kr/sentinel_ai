"use client";

import * as React from "react";
import { ArrowRight, Bot, User, Loader2, Plus, ChevronDown, BookOpen, ExternalLink } from "lucide-react";
import { ApiClient } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { materialLight } from "react-syntax-highlighter/dist/cjs/styles/prism";

interface Citation {
  document_title?: string;
  page_number?: number;
  chunk_text?: string;
  confidence?: number;
}

interface EvidenceConfidence {
  overall?: string;
  ocr_quality?: string;
  source_page?: number;
  cross_check?: string;
  source_count?: number;
  citation_count?: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  model_used?: string;
  citations?: Citation[];
  evidence_confidence?: EvidenceConfidence;
}

export function ChatInterface({ 
  sessionId: externalSessionId,
  onSessionCreated, 
}: { 
  sessionId?: string | null;
  onSessionCreated?: (sessionId: string) => void;
}) {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [sessionId, setSessionId] = React.useState<string | null>(externalSessionId || null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // Sync external session id
  React.useEffect(() => {
    if (externalSessionId !== undefined) {
      setSessionId(externalSessionId || null);
    }
  }, [externalSessionId]);

  // Load existing session messages (FR9.3 — resume)
  React.useEffect(() => {
    if (sessionId) {
      loadSessionMessages(sessionId);
    } else {
      setMessages([]);
    }
  }, [sessionId]);

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function loadSessionMessages(sid: string) {
    try {
      const msgs = await ApiClient.getMessages(sid);
      setMessages(
        msgs.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at),
          model_used: m.model_used,
          citations: m.citations,
          evidence_confidence: m.evidence_confidence_json,
        }))
      );
    } catch (err) {
      console.error("Failed to load messages", err);
    }
  }

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userText = input;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: userText,
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const session = await ApiClient.createSession(userText.substring(0, 80));
        currentSessionId = session.id;
        setSessionId(currentSessionId);
        onSessionCreated?.(currentSessionId);
      }
      
      if (userText.trim().startsWith("/task")) {
        const goal = userText.replace("/task", "").trim();
        const taskResult = await ApiClient.createTask(goal, currentSessionId!);
        
        const assistantMsg: Message = {
          id: Date.now().toString(),
          role: "assistant",
          content: `✅ Task created (ID: ${taskResult.task_id}).\n\nGoal: "${goal}"\nStatus: Accepted — running asynchronously.\n\nYou can monitor progress in **Agent Tasks** or via WebSocket at \`/tasks/${taskResult.task_id}/stream\`.`,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMsg]);
      } else {
        const response = await ApiClient.sendMessage(currentSessionId!, userText);
        
        const assistantMsg: Message = {
          id: response.id || Date.now().toString(),
          role: "assistant",
          content: response.content,
          timestamp: new Date(),
          model_used: response.model_used,
          citations: response.citations,
          evidence_confidence: response.evidence_confidence_json,
        };
        setMessages(prev => [...prev, assistantMsg]);
      }
    } catch (err: any) {
      console.error(err);
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: "assistant",
        content: `⚠️ Error: ${err.message || 'Failed to process request.'}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      {!isEmpty && (
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 scroll-smooth bg-white"
        >
          <div className="max-w-3xl mx-auto space-y-8">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                {/* Avatar + Name */}
                <div className={`flex items-center space-x-2 mb-1.5 ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                  <div className={`h-6 w-6 rounded-full flex items-center justify-center text-white ${
                    msg.role === 'user' ? 'bg-indigo-600' : 'bg-gray-800'
                  }`}>
                    {msg.role === 'user' ? <User size={12} /> : <Bot size={12} />}
                  </div>
                  <span className="font-semibold text-[13px] text-gray-800">
                    {msg.role === 'user' ? 'You' : 'SENTINEL'}
                  </span>
                  {msg.model_used && (
                    <span className="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
                      {msg.model_used}
                    </span>
                  )}
                </div>

                {/* Message content */}
                <div className={`text-gray-700 text-[14px] leading-relaxed prose prose-sm max-w-none prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 ${
                  msg.role === 'user'
                    ? 'bg-indigo-50/50 border border-indigo-100 px-4 py-2.5 rounded-2xl rounded-tr-sm mr-8 text-right'
                    : 'pl-8'
                }`}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ node, inline, className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || "");
                        return !inline && match ? (
                          <div className="rounded-md overflow-hidden my-4 border border-gray-200">
                            <div className="bg-gray-100 px-4 py-2 text-xs font-mono text-gray-600 border-b border-gray-200">
                              {match[1]}
                            </div>
                            <SyntaxHighlighter
                              style={materialLight as any}
                              language={match[1]}
                              PreTag="div"
                              className="!m-0 text-sm"
                              {...props}
                            >
                              {String(children).replace(/\n$/, "")}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <code className="bg-gray-100 text-pink-600 px-1 py-0.5 rounded text-[13px] font-mono" {...props}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>

                {/* FR9.4 — Citations displayed inline */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="pl-8 mt-3">
                    <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                      <div className="flex items-center space-x-1.5 mb-2">
                        <BookOpen className="h-3.5 w-3.5 text-blue-600" />
                        <span className="text-[11px] font-semibold text-blue-700 uppercase tracking-wide">Sources</span>
                      </div>
                      <div className="space-y-1.5">
                        {msg.citations.map((cite, i) => (
                          <div key={i} className="flex items-start space-x-2 text-[12px] text-blue-800">
                            <span className="font-mono bg-blue-100 text-blue-700 px-1 py-0.5 rounded text-[10px] flex-shrink-0">
                              [{i + 1}]
                            </span>
                            <span>
                              {cite.document_title || "Document"}
                              {cite.page_number && ` — Page ${cite.page_number}`}
                              {cite.confidence && ` (${(cite.confidence * 100).toFixed(0)}%)`}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* FR9.4 — Evidence confidence breakdown */}
                {msg.evidence_confidence && (
                  <div className="pl-8 mt-2">
                    <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-2.5 text-[11px]">
                      <span className="font-semibold text-emerald-700">Evidence: </span>
                      <span className={`font-bold ${
                        msg.evidence_confidence.overall === "HIGH" ? "text-emerald-600" :
                        msg.evidence_confidence.overall === "MEDIUM" ? "text-amber-600" :
                        "text-red-600"
                      }`}>
                        {msg.evidence_confidence.overall || "N/A"}
                      </span>
                      {msg.evidence_confidence.source_count !== undefined && (
                        <span className="text-emerald-600 ml-2">
                          • {msg.evidence_confidence.source_count} sources
                        </span>
                      )}
                      {msg.evidence_confidence.citation_count !== undefined && (
                        <span className="text-emerald-600 ml-2">
                          • {msg.evidence_confidence.citation_count} citations
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex items-center space-x-2 pl-8 animate-pulse">
                <Loader2 size={14} className="animate-spin text-gray-400" />
                <span className="text-sm text-gray-400">SENTINEL is thinking...</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className={`flex flex-col w-full px-4 transition-all duration-500 ease-in-out ${
        isEmpty ? 'flex-1 items-center justify-center bg-[#f9fafb]' : 'bg-white pb-4 pt-2 border-t border-gray-100'
      }`}>
        
        {isEmpty && (
          <div className="mb-6 flex items-center space-x-2 text-gray-400 font-medium text-sm">
            <span>New Conversation</span>
            <ChevronDown size={14} />
          </div>
        )}

        <div className="w-full max-w-3xl bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden flex flex-col transition-all focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-400">
          
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask anything, @ to mention, / for actions"
            className="w-full bg-transparent text-gray-800 text-[14px] px-4 py-3 focus:outline-none resize-none placeholder:text-gray-400"
            rows={1}
            style={{ minHeight: '52px' }}
            disabled={isLoading}
          />

          <div className="flex items-center justify-between px-3 pb-2.5">
            <div className="flex items-center space-x-2">
              <button className="h-7 w-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 transition-colors">
                <Plus size={15} />
              </button>
              <span className="text-[11px] text-gray-400 font-medium">
                Groq / Gemini API
              </span>
            </div>

            <button 
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className={`h-7 w-7 flex items-center justify-center rounded-full transition-colors ${
                input.trim() ? 'bg-gray-900 text-white hover:bg-gray-800' : 'bg-gray-200 text-gray-400'
              }`}
            >
              <ArrowRight size={14} />
            </button>
          </div>
        </div>

        {isEmpty && (
          <p className="mt-4 text-[11px] text-gray-400 text-center max-w-md">
            SENTINEL is a sovereign AI workbench. Type <code className="bg-gray-100 px-1 rounded text-gray-500">/task</code> to create an async agent task, or just ask a question.
          </p>
        )}
      </div>
    </div>
  );
}
