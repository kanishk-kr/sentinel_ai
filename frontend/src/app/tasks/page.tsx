"use client";

import * as React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { PlayCircle, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function TasksPage() {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [tasks, setTasks] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedTask, setSelectedTask] = React.useState<any>(null);

  React.useEffect(() => {
    async function loadTasks() {
      try {
        const data = await ApiClient.listTasks();
        setTasks(data);
      } catch (err) {
        console.error("Failed to fetch tasks", err);
      } finally {
        setLoading(false);
      }
    }
    
    loadTasks();
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleViewTask(taskId: string) {
    try {
      const detail = await ApiClient.getTask(taskId);
      setSelectedTask(detail);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-white text-gray-900">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        <Topbar toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold tracking-tight">Agent Tasks</h1>
              <p className="text-sm text-gray-500 mt-0.5">Monitor background agent executions and pipelines (FR3.5, FR9.5).</p>
            </div>
            <button 
              onClick={() => router.push('/')}
              className="bg-indigo-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-indigo-700 transition-colors shadow-sm"
            >
              New Task
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Task List */}
            <div className={`${selectedTask ? 'lg:col-span-2' : 'lg:col-span-3'} rounded-xl border border-gray-200 overflow-hidden`}>
              <table className="w-full text-xs text-left">
                <thead className="text-[10px] uppercase text-gray-400 border-b border-gray-100 bg-gray-50">
                  <tr>
                    <th className="px-4 py-2.5 font-medium">Task ID</th>
                    <th className="px-4 py-2.5 font-medium">Goal</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                    <th className="px-4 py-2.5 font-medium">Started</th>
                    <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {loading && tasks.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-1" />
                        Loading tasks...
                      </td>
                    </tr>
                  ) : tasks.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                        No agent tasks found. Start a new task in the Agent Workspace.
                      </td>
                    </tr>
                  ) : (
                    tasks.map((task) => (
                      <tr key={task.id} className="hover:bg-gray-50 transition-colors cursor-pointer" onClick={() => handleViewTask(task.id)}>
                        <td className="px-4 py-3 font-mono text-[10px] text-gray-400">{task.id.split("-")[0]}...</td>
                        <td className="px-4 py-3 font-medium text-gray-700 max-w-xs truncate" title={task.goal}>{task.goal}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={task.status} />
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {new Date(task.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button className="text-indigo-600 hover:text-indigo-800 font-medium text-[10px]">
                            View Details
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Task Detail Panel */}
            {selectedTask && (
              <div className="lg:col-span-1 rounded-xl border border-gray-200 p-4 overflow-y-auto">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-800">Task Details</h3>
                  <button onClick={() => setSelectedTask(null)} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
                </div>
                
                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-gray-400 block mb-0.5">Goal</span>
                    <span className="text-gray-700 font-medium">{selectedTask.goal}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block mb-0.5">Status</span>
                    <StatusBadge status={selectedTask.status} />
                  </div>
                  {selectedTask.error_message && (
                    <div className="bg-red-50 border border-red-100 rounded-lg p-2 text-red-600">
                      {selectedTask.error_message}
                    </div>
                  )}
                  {selectedTask.steps && selectedTask.steps.length > 0 && (
                    <div>
                      <span className="text-gray-400 block mb-1.5">Steps ({selectedTask.steps.length})</span>
                      <div className="space-y-1.5">
                        {selectedTask.steps.map((step: any, i: number) => (
                          <div key={step.id} className="flex items-start space-x-2 p-2 bg-gray-50 rounded-lg border border-gray-100">
                            <span className="text-[10px] text-gray-400 font-mono">{i + 1}</span>
                            <div className="flex-1 min-w-0">
                              <p className="text-gray-700 truncate">{step.description || step.tool_used || "Step"}</p>
                              <div className="flex items-center space-x-2 mt-0.5">
                                <StatusBadge status={step.status} />
                                {step.model_used && <span className="text-[9px] text-gray-400">{step.model_used}</span>}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "COMPLETED":
    case "VERIFIED":
    case "COMMITTED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700">
          <CheckCircle2 className="w-3 h-3 mr-0.5" />
          {status === "COMPLETED" ? "Completed" : status}
        </span>
      );
    case "FAILED":
    case "REJECTED":
    case "VERIFY_FAILED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700">
          <XCircle className="w-3 h-3 mr-0.5" />
          {status}
        </span>
      );
    case "RUNNING":
    case "PLANNING":
    case "EXECUTING":
    case "AUTHORIZED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-700 animate-pulse">
          <PlayCircle className="w-3 h-3 mr-0.5" />
          {status}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600">
          <Clock className="w-3 h-3 mr-0.5" />
          {status}
        </span>
      );
  }
}
