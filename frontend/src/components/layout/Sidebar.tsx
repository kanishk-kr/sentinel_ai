"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  Plus,
  History,
  Clock,
  MessageSquare,
  Settings,
  ChevronDown,
  ChevronRight,
  Trash2,
  Loader2,
  Shield,
  Database,
  ListTodo,
  Lock,
  FolderPlus,
  Folder,
  FolderOpen
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

interface ChatSession {
  id: string;
  title: string;
  message_count: number;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

interface Project {
  id: string;
  name: string;
  description: string | null;
  working_dir: string;
  session_count: number;
  created_at: string;
  updated_at: string;
}

export function Sidebar({ 
  isOpen, 
  toggleSidebar,
  activeSessionId,
  activeProjectId,
  onProjectSelect,
  onSessionSelect,
  onNewConversation,
}: { 
  isOpen: boolean; 
  toggleSidebar: () => void;
  activeSessionId?: string | null;
  activeProjectId?: string | null;
  onProjectSelect?: (projectId: string | null) => void;
  onSessionSelect?: (sessionId: string) => void;
  onNewConversation?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [sessions, setSessions] = React.useState<ChatSession[]>([]);
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [expandedProjects, setExpandedProjects] = React.useState<Set<string>>(new Set());
  const [showNewProject, setShowNewProject] = React.useState(false);
  const [newProjectName, setNewProjectName] = React.useState("");
  const [newProjectDesc, setNewProjectDesc] = React.useState("");
  const [newProjectDir, setNewProjectDir] = React.useState("");
  const [creatingProject, setCreatingProject] = React.useState(false);

  // Load sessions and projects from API
  React.useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [sessionData, projectData] = await Promise.all([
        ApiClient.listSessions().catch(() => ({ sessions: [] })),
        ApiClient.listProjects().catch(() => ({ projects: [] })),
      ]);
      setSessions(sessionData.sessions || []);
      setProjects(projectData.projects || []);
    } catch (err) {
      console.error("Failed to load sidebar data", err);
    } finally {
      setLoading(false);
    }
  }

  // Auto-expand the project that contains the active session
  React.useEffect(() => {
    if (activeSessionId && sessions.length > 0) {
      const activeSession = sessions.find(s => s.id === activeSessionId);
      if (activeSession?.project_id) {
        setExpandedProjects(prev => new Set([...prev, activeSession.project_id!]));
      }
    }
  }, [activeSessionId, sessions]);

  function toggleProject(projectId: string) {
    setExpandedProjects(prev => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  }

  async function handleNewConversation() {
    router.push('/');
    if (window.innerWidth < 1024) toggleSidebar();
  }

  async function handleDeleteSession(e: React.MouseEvent, sessionId: string) {
    e.stopPropagation();
    e.preventDefault();
    try {
      await ApiClient.deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        router.push('/');
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  }

  async function handleCreateProject() {
    if (!newProjectName.trim() || !newProjectDir.trim()) return;
    try {
      setCreatingProject(true);
      await ApiClient.createProject(newProjectName, newProjectDesc, newProjectDir);
      setNewProjectName("");
      setNewProjectDesc("");
      setNewProjectDir("");
      setShowNewProject(false);
      await loadData();
    } catch (err) {
      console.error("Failed to create project", err);
      alert("Failed to create project");
    } finally {
      setCreatingProject(false);
    }
  }

  async function handleDeleteProject(e: React.MouseEvent, projectId: string) {
    e.stopPropagation();
    if (!confirm("Delete this project? Conversations will be kept but unlinked.")) return;
    try {
      await ApiClient.deleteProject(projectId);
      await loadData();
    } catch (err) {
      console.error("Failed to delete project", err);
    }
  }

  // Group sessions by project
  const sessionsByProject = React.useMemo(() => {
    const grouped: Record<string, ChatSession[]> = {};
    const orphaned: ChatSession[] = [];
    for (const session of sessions) {
      if (session.project_id) {
        if (!grouped[session.project_id]) grouped[session.project_id] = [];
        grouped[session.project_id].push(session);
      } else {
        orphaned.push(session);
      }
    }
    return { grouped, orphaned };
  }, [sessions]);

  return (
    <aside 
      className={`fixed inset-y-0 left-0 z-50 w-64 bg-[#f9fafb] transition-transform duration-300 ease-in-out ${
        isOpen ? "translate-x-0" : "-translate-x-full"
      } flex flex-col border-r border-gray-200 lg:translate-x-0 lg:static lg:h-full`}
    >
      {/* New Conversation button */}
      <div className="p-3">
        <button
          onClick={handleNewConversation}
          className="w-full flex items-center justify-start bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 shadow-sm rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
        >
          <Plus className="mr-2 h-4 w-4 text-gray-400" />
          New Conversation
        </button>
      </div>

      {/* Navigation */}
      <div className="px-2 space-y-0.5">
        <NavItem icon={<History />} label="Conversation History" href="/" active={pathname === "/"} />
        <NavItem icon={<ListTodo />} label="Agent Tasks" href="/tasks" active={pathname === "/tasks"} />
        <NavItem icon={<Database />} label="Knowledge Base" href="/knowledge" active={pathname === "/knowledge"} />
        <NavItem icon={<Lock />} label="Admin Console" href="/admin" active={pathname === "/admin"} />
      </div>

      {/* Projects & Conversations */}
      <div className="flex-1 overflow-y-auto mt-4 px-2">
        {/* Projects Header */}
        <div className="flex items-center justify-between px-2 py-2 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
          <span>Projects</span>
          <button 
            onClick={() => setShowNewProject(!showNewProject)} 
            className="hover:text-gray-600 transition-colors"
            title="New Project"
          >
            <FolderPlus className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* New Project Form (inline) */}
        {showNewProject && (
          <div className="mx-1 mb-2 p-2.5 bg-white rounded-lg border border-indigo-200 shadow-sm">
            <input
              type="text"
              placeholder="Project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="w-full text-xs px-2 py-1.5 rounded border border-gray-200 focus:outline-none focus:border-indigo-300 mb-1.5"
              autoFocus
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={newProjectDesc}
              onChange={(e) => setNewProjectDesc(e.target.value)}
              className="w-full text-xs px-2 py-1.5 rounded border border-gray-200 focus:outline-none focus:border-indigo-300 mb-1.5"
            />
            <div className="flex items-center mb-2">
              <input
                type="text"
                placeholder="Working directory absolute path (e.g. /Users/...)"
                value={newProjectDir}
                onChange={(e) => setNewProjectDir(e.target.value)}
                className="flex-1 text-xs px-2 py-1.5 rounded border border-gray-200 focus:outline-none focus:border-indigo-300"
              />
            </div>
            <div className="flex gap-1.5">
              <button
                onClick={handleCreateProject}
                disabled={creatingProject || !newProjectName.trim() || !newProjectDir.trim()}
                className="flex-1 text-[10px] font-medium bg-indigo-600 text-white py-1.5 rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {creatingProject ? "Creating..." : "Create Project"}
              </button>
              <button
                onClick={() => setShowNewProject(false)}
                className="text-[10px] text-gray-500 px-2 py-1.5 rounded hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
        
        {loading ? (
          <div className="flex items-center justify-center py-8 text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        ) : (
          <>
            {/* Project Tree */}
            {projects.map((project) => {
              const isExpanded = expandedProjects.has(project.id);
              const projectSessions = sessionsByProject.grouped[project.id] || [];
              
              return (
                <div key={project.id} className="mb-0.5">
                  {/* Project Header */}
                  <div 
                    className={`flex items-center w-full px-2 py-1.5 text-[13px] rounded-lg transition-colors cursor-pointer group ${
                      activeProjectId === project.id
                        ? "bg-indigo-50 text-indigo-700"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                    }`}
                    onClick={() => {
                      toggleProject(project.id);
                      onProjectSelect?.(project.id);
                    }}
                  >
                    <span className="mr-1.5 flex-shrink-0">
                      {isExpanded ? (
                        <ChevronDown className="h-3 w-3 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-3 w-3 text-gray-400" />
                      )}
                    </span>
                    <span className="mr-1.5 flex-shrink-0">
                      {isExpanded ? (
                        <FolderOpen className="h-3.5 w-3.5 text-indigo-400" />
                      ) : (
                        <Folder className="h-3.5 w-3.5 text-gray-400" />
                      )}
                    </span>
                    <span className="truncate flex-1 font-medium">{project.name}</span>
                    <button
                      onClick={(e) => handleDeleteProject(e, project.id)}
                      className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all ml-1"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>

                  {/* Expanded Sessions */}
                  {isExpanded && (
                    <div className="ml-5 mt-0.5 space-y-0.5">
                      {projectSessions.length === 0 ? (
                        <p className="px-2 py-1 text-[11px] text-gray-400 italic">
                          No conversations yet
                        </p>
                      ) : (
                        projectSessions.map((session) => (
                          <Link
                            href={`/c/${session.id}`}
                            key={session.id}
                            onClick={() => window.innerWidth < 1024 && toggleSidebar()}
                            className={`flex items-center justify-between w-full px-2 py-1 text-[12px] rounded-md transition-colors group ${
                              activeSessionId === session.id
                                ? "bg-gray-100 text-gray-900"
                                : "text-gray-500 hover:bg-gray-50 hover:text-gray-800"
                            }`}
                          >
                            <span className="truncate flex-1">
                              <MessageSquare className="inline h-3 w-3 mr-1.5 text-gray-400" />
                              {session.title || "Untitled"}
                            </span>
                            <button
                              onClick={(e) => handleDeleteSession(e, session.id)}
                              className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all"
                            >
                              <Trash2 className="h-2.5 w-2.5" />
                            </button>
                          </Link>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Orphaned Conversations (no project) */}
            {sessionsByProject.orphaned.length > 0 && (
              <>
                <div className="flex items-center justify-between px-2 py-2 mt-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                  <span>Conversations</span>
                  <button onClick={handleNewConversation} className="hover:text-gray-600 transition-colors">
                    <Plus className="h-3 w-3" />
                  </button>
                </div>
                <div className="space-y-0.5">
                  {sessionsByProject.orphaned.map((session) => (
                    <Link
                      href={`/c/${session.id}`}
                      key={session.id}
                      onClick={() => window.innerWidth < 1024 && toggleSidebar()}
                      className={`flex items-center justify-between w-full px-2 py-1.5 text-sm rounded-lg transition-colors group ${
                        activeSessionId === session.id
                          ? "bg-gray-100 text-gray-900"
                          : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                      }`}
                    >
                      <span className="truncate flex-1 text-left text-[13px]">{session.title || "Untitled"}</span>
                      <div className="flex items-center ml-2 space-x-1">
                        {activeSessionId === session.id && (
                          <span className="text-[10px] text-gray-400 mr-1">{session.message_count} msgs</span>
                        )}
                        <button
                          onClick={(e) => handleDeleteSession(e, session.id)}
                          className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </Link>
                  ))}
                </div>
              </>
            )}

            {/* Empty state */}
            {projects.length === 0 && sessionsByProject.orphaned.length === 0 && (
              <div className="px-2 py-8 text-center">
                <Folder className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                <p className="text-xs text-gray-400">No projects yet.</p>
                <button
                  onClick={() => setShowNewProject(true)}
                  className="mt-2 text-xs text-indigo-500 hover:text-indigo-700 font-medium transition-colors"
                >
                  Create your first project
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Settings */}
      <div className="p-3 border-t border-gray-200">
        <Button variant="ghost" className="w-full justify-start text-gray-500 hover:bg-gray-100 hover:text-gray-900 rounded-lg text-sm">
          <Settings className="h-4 w-4 mr-3" />
          Settings
        </Button>
      </div>
    </aside>
  );
}

function NavItem({ icon, label, href, active }: { icon: React.ReactNode; label: string; href: string; active?: boolean }) {
  return (
    <Link href={href}>
      <button className={`flex items-center w-full px-2 py-2 text-[13px] rounded-lg transition-colors ${
        active ? "bg-gray-100 text-gray-900 font-medium" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
      }`}>
        <span className="mr-3 h-4 w-4 flex-shrink-0">{icon}</span>
        {label}
      </button>
    </Link>
  );
}
