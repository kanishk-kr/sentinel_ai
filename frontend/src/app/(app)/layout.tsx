"use client";

import * as React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { useParams } from "next/navigation";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const params = useParams();
  
  // Extract session ID from the URL if we are on a chat route (/c/[id])
  const activeSessionId = typeof params.id === "string" ? params.id : null;

  return (
    <div className="flex h-screen overflow-hidden bg-white text-gray-900 font-sans">
      <Sidebar 
        isOpen={sidebarOpen} 
        toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        activeSessionId={activeSessionId}
      />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10 bg-white">
        <Topbar toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-auto flex flex-col relative">
          {children}
        </main>
      </div>
    </div>
  );
}
