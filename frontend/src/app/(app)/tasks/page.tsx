"use client";

import * as React from "react";
import { PlayCircle, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { useRouter } from "next/navigation";
import { TaskDetailPanel, StatusBadge } from "@/components/chat/TaskDetailPanel";

export default function TasksPage() {
  const router = useRouter();
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
    <div className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
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
              <div className="lg:col-span-1 rounded-xl border border-gray-200 p-4">
                <TaskDetailPanel task={selectedTask} onClose={() => setSelectedTask(null)} />
              </div>
            )}
          </div>
    </div>
  );
}
