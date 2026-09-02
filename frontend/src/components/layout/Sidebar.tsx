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
  Trash2,
  Loader2,
  Shield,
  Database,
  ListTodo,
  Lock
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

interface ChatSession {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export function Sidebar({ 
  isOpen, 
  toggleSidebar,
  activeSessionId,
  onSessionSelect,
  onNewConversation,
}: { 
  isOpen: boolean; 
  toggleSidebar: () => void;
  activeSessionId?: string | null;
  onSessionSelect?: (sessionId: string) => void;
  onNewConversation?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [sessions, setSessions] = React.useState<ChatSession[]>([]);
  const [loading, setLoading] = React.useState(true);

  // Load sessions from API (FR9.3)
  React.useEffect(() => {
    loadSessions();
  }, []);

  async function loadSessions() {
    try {
      setLoading(true);
      const data = await ApiClient.listSessions();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error("Failed to load sessions", err);
    } finally {
      setLoading(false);
    }
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

      {/* Sessions list — loaded from API (FR9.3) */}
      <div className="flex-1 overflow-y-auto mt-4 px-2">
        <div className="flex items-center justify-between px-2 py-2 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
          <span>Conversations</span>
          <button onClick={handleNewConversation} className="hover:text-gray-600 transition-colors">
            <Plus className="h-3 w-3" />
          </button>
        </div>
        
        <div className="mt-1 space-y-0.5">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="px-2 py-4 text-xs text-gray-400 text-center">
              No conversations yet.
            </p>
          ) : (
            sessions.map((session) => (
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
            ))
          )}
        </div>
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
