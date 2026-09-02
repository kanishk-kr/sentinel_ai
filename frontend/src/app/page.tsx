"use client";

import * as React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  const [chatKey, setChatKey] = React.useState(0); // Forces ChatInterface to remount

  function handleSessionSelect(sessionId: string) {
    setActiveSessionId(sessionId);
    setChatKey(prev => prev + 1);
  }

  function handleNewConversation() {
    setActiveSessionId(null);
    setChatKey(prev => prev + 1);
  }

  function handleSessionCreated(sessionId: string) {
    setActiveSessionId(sessionId);
  }
  
  return (
    <div className="flex h-screen overflow-hidden bg-white text-gray-900 font-sans">
      <Sidebar 
        isOpen={sidebarOpen} 
        toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        activeSessionId={activeSessionId}
        onSessionSelect={handleSessionSelect}
        onNewConversation={handleNewConversation}
      />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10 bg-white">
        <Topbar toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-auto flex flex-col relative">
          <ChatInterface 
            key={chatKey}
            sessionId={activeSessionId} 
            onSessionCreated={handleSessionCreated}
          />
        </main>
      </div>
    </div>
  );
}
