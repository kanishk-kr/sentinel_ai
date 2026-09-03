"use client";

import * as React from "react";
import { CheckCircle2, XCircle, Clock } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "COMPLETED":
    case "VERIFIED":
    case "COMMITTED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700">
          <CheckCircle2 className="w-3 h-3 mr-1" />
          {status}
        </span>
      );
    case "FAILED":
    case "VERIFY_FAILED":
    case "REJECTED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700">
          <XCircle className="w-3 h-3 mr-1" />
          {status}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-700">
          <Clock className="w-3 h-3 mr-1" />
          {status}
        </span>
      );
  }
}

export function TaskDetailPanel({ task, onClose }: { task: any; onClose?: () => void }) {
  if (!task) return null;

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex items-center justify-between mb-3 border-b border-gray-100 pb-2">
        <h3 className="text-sm font-semibold text-gray-800">Task Details</h3>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xs p-1">✕</button>
        )}
      </div>
      
      <div className="space-y-4 text-xs overflow-y-auto flex-1 pb-4">
        <div>
          <span className="text-gray-400 block mb-0.5 font-medium">Goal</span>
          <span className="text-gray-700">{task.goal}</span>
        </div>
        <div>
          <span className="text-gray-400 block mb-0.5 font-medium">Status</span>
          <StatusBadge status={task.status} />
        </div>
        
        {task.error_message && (
          <div className="bg-red-50 border border-red-100 rounded-lg p-2 text-red-600">
            {task.error_message}
          </div>
        )}
        
        {task.steps && task.steps.length > 0 && (
          <div>
            <span className="text-gray-400 block mb-1.5 font-medium">Steps ({task.steps.length})</span>
            <div className="space-y-1.5">
              {task.steps.map((step: any, i: number) => (
                <div key={step.id} className="flex items-start space-x-2 p-2 bg-gray-50 rounded-lg border border-gray-100">
                  <span className="text-[10px] text-gray-400 font-mono mt-0.5">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-700 truncate">{step.description || step.tool_used || "Step"}</p>
                    <div className="flex items-center space-x-2 mt-1 mb-1">
                      <StatusBadge status={step.status} />
                      {step.model_used && <span className="text-[9px] text-gray-400">{step.model_used}</span>}
                    </div>
                    {step.result && (
                      <div className="mt-2 text-[11px] bg-white p-2.5 rounded border border-gray-200 text-gray-700 max-h-64 overflow-y-auto break-words prose prose-sm max-w-none prose-p:leading-snug prose-pre:bg-gray-50 prose-pre:text-gray-800">
                        {(() => {
                          const resultString = typeof step.result === 'string' 
                            ? step.result 
                            : (step.result && step.result.output && typeof step.result.output === 'string')
                              ? step.result.output
                              : null;
                              
                          if (resultString) {
                            return <ReactMarkdown remarkPlugins={[remarkGfm]}>{resultString}</ReactMarkdown>;
                          }
                          return <pre className="whitespace-pre-wrap">{JSON.stringify(step.result, null, 2)}</pre>;
                        })()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
