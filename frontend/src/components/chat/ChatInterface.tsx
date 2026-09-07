"use client";

import * as React from "react";
import { ArrowRight, Bot, User, Loader2, Plus, ChevronDown, BookOpen, ExternalLink, Folder, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { ApiClient } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { materialLight } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { TaskDetailPanel } from "@/components/chat/TaskDetailPanel";
import { FileExplorerPane } from "@/components/chat/FileExplorerPane";

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
  const router = useRouter();
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [sessionId, setSessionId] = React.useState<string | null>(externalSessionId || null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  
  // Sidebar state
  const [sidebarTaskId, setSidebarTaskId] = React.useState<string | null>(null);
  const [sidebarTaskDetail, setSidebarTaskDetail] = React.useState<any>(null);
  const [sidebarLoading, setSidebarLoading] = React.useState(false);

  // Projects state
  const [projects, setProjects] = React.useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = React.useState<string | null>(null);
  const [showProjectPicker, setShowProjectPicker] = React.useState(false);
  
  // Current session state
  const [currentSession, setCurrentSession] = React.useState<any>(null);

  // Load projects
  React.useEffect(() => {
    ApiClient.listProjects()
      .then(data => {
        setProjects(data.projects || []);
        if (data.projects?.length > 0 && !selectedProjectId) {
          // Default to first project if none selected
          setSelectedProjectId(data.projects[0].id);
        }
      })
      .catch(err => console.error("Failed to load projects", err));
  }, []);

  // Approvals state
  const [pendingApprovals, setPendingApprovals] = React.useState<any[]>([]);

  // Load task details when sidebar opens
  React.useEffect(() => {
    if (sidebarTaskId) {
      setSidebarLoading(true);
      ApiClient.getTask(sidebarTaskId)
        .then(data => {
          setSidebarTaskDetail(data);
          setSidebarLoading(false);
        })
        .catch(err => {
          console.error("Failed to load task details", err);
          setSidebarLoading(false);
        });
    } else {
      setSidebarTaskDetail(null);
    }
  }, [sidebarTaskId]);

  const extractTaskId = (content: string) => {
    const match = content.match(/\(ID: ([a-f0-9\-]+)\)/i);
    return match ? match[1] : null;
  };

  // Sync external session id
  React.useEffect(() => {
    if (externalSessionId !== undefined) {
      setSessionId(externalSessionId || null);
    }
  }, [externalSessionId]);

  // Poll for pending approvals
  React.useEffect(() => {
    const fetchApprovals = async () => {
      try {
        const approvals = await ApiClient.getPendingApprovals();
        setPendingApprovals(approvals || []);
      } catch (err) {
        // ignore polling errors
      }
    };
    
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 5000);
    return () => clearInterval(interval);
  }, []);

  // Load existing session messages (FR9.3 — resume)
  React.useEffect(() => {
    if (sessionId) {
      loadSessionMessages(sessionId);
      ApiClient.getSession(sessionId)
        .then(data => setCurrentSession(data))
        .catch(err => console.error("Failed to load session", err));
    } else {
      setMessages([]);
      setCurrentSession(null);
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
        const session = await ApiClient.createSession(userText.substring(0, 80), selectedProjectId || undefined);
        currentSessionId = session.id;
        setCurrentSession(session);
        setSessionId(currentSessionId);
        onSessionCreated?.(currentSessionId);
        // Shallow update URL without unmounting the component while it waits for the LLM response
        window.history.replaceState(null, '', '/c/' + currentSessionId);
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
    <div className="flex h-full w-full overflow-hidden bg-white">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Pending Approvals Banner */}
        {pendingApprovals.length > 0 && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-3 flex flex-col space-y-2">
            <div className="flex items-center text-amber-800 font-semibold text-sm">
              <Shield size={16} className="mr-2" />
              Pending Human Approvals ({pendingApprovals.length})
            </div>
            {pendingApprovals.map((approval) => (
              <div key={approval.id} className="bg-white border border-amber-200 rounded p-3 flex items-center justify-between shadow-sm">
                <div>
                  <div className="text-sm font-medium text-gray-800">{approval.action_description}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    Risk Tier: <span className="font-semibold">{approval.risk_tier}</span> | 
                    Requested: {new Date(approval.created_at).toLocaleString()}
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={async () => {
                      try {
                        await ApiClient.decideApproval(approval.id, "REJECTED");
                        setPendingApprovals(prev => prev.filter(a => a.id !== approval.id));
                      } catch (e) {
                        alert("Failed to reject approval");
                      }
                    }}
                    className="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded transition-colors border border-red-200"
                  >
                    Deny
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        await ApiClient.decideApproval(approval.id, "APPROVED");
                        setPendingApprovals(prev => prev.filter(a => a.id !== approval.id));
                      } catch (e) {
                        alert("Failed to approve");
                      }
                    }}
                    className="px-3 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded transition-colors border border-emerald-200"
                  >
                    Approve
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Messages Area */}
        {!isEmpty && (
          <div 
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 scroll-smooth"
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
                  
                  {/* Task Actions */}
                  {msg.role === "assistant" && extractTaskId(msg.content) && (
                    <div className="mt-3 w-full">
                      <button 
                        onClick={() => setSidebarTaskId(sidebarTaskId === extractTaskId(msg.content) ? null : extractTaskId(msg.content))}
                        className="text-xs font-medium bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-1.5 rounded-full transition-colors border border-indigo-200"
                      >
                        {sidebarTaskId === extractTaskId(msg.content) ? "Close Task Details" : "View Task Details"}
                      </button>
                      
                      {sidebarTaskId === extractTaskId(msg.content) && (
                        <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden bg-white max-h-[500px] flex flex-col shadow-sm">
                          {sidebarLoading ? (
                            <div className="p-8 flex items-center justify-center text-gray-400">
                              <Loader2 className="w-5 h-5 animate-spin" />
                            </div>
                          ) : (
                            <div className="overflow-y-auto p-4 flex-1">
                              <TaskDetailPanel task={sidebarTaskDetail} onClose={() => setSidebarTaskId(null)} />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
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
          <div className="mb-6 flex flex-col items-center">
            <div className="flex items-center space-x-2 text-gray-400 font-medium text-sm mb-2">
              <span>New Conversation</span>
            </div>
            
            <div className="relative">
              <button 
                onClick={() => setShowProjectPicker(!showProjectPicker)}
                className="flex items-center space-x-2 bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-[13px] font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
              >
                <Folder size={14} className="text-indigo-500" />
                <span>
                  {selectedProjectId 
                    ? projects.find(p => p.id === selectedProjectId)?.name || "Unknown Project"
                    : "No Project (Global)"}
                </span>
                <ChevronDown size={14} className="text-gray-400" />
              </button>

              {showProjectPicker && (
                <div className="absolute top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1 max-h-64 overflow-y-auto">
                  <button
                    onClick={() => {
                      setSelectedProjectId(null);
                      setShowProjectPicker(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-[13px] hover:bg-gray-50 flex items-center space-x-2 ${
                      selectedProjectId === null ? "bg-indigo-50 text-indigo-700" : "text-gray-700"
                    }`}
                  >
                    <Folder size={14} className="text-gray-400" />
                    <span>No Project (Global)</span>
                  </button>
                  <div className="border-t border-gray-100 my-1"></div>
                  {projects.map(project => (
                    <button
                      key={project.id}
                      onClick={() => {
                        setSelectedProjectId(project.id);
                        setShowProjectPicker(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-[13px] hover:bg-gray-50 flex items-center space-x-2 ${
                        selectedProjectId === project.id ? "bg-indigo-50 text-indigo-700" : "text-gray-700"
                      }`}
                    >
                      <Folder size={14} className="text-indigo-500" />
                      <span className="truncate flex-1">{project.name}</span>
                      {project.working_dir && (
                        <span className="text-[10px] text-gray-400 truncate max-w-[80px]" title={project.working_dir}>
                          {project.working_dir.split('/').pop()}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="w-full max-w-3xl mx-auto bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden flex flex-col transition-all focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-400">
          
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
      
      {/* File Explorer Right Pane (Phase 7) */}
      {currentSession?.project_id && (
        <FileExplorerPane projectId={currentSession.project_id} />
      )}
    </div>
  );
}
