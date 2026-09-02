"use client";

import * as React from "react";
import { FileCode, FileText, CheckCircle, ShieldAlert, GitCommit, Download, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

interface ArtifactData {
  id: string;
  task_id: string;
  artifact_type: string;
  title: string;
  current_version: number;
  status: string;
  versions: any[];
  provenance?: any[];
  created_at: string;
}

export function ArtifactViewer() {
  const [artifacts, setArtifacts] = React.useState<ArtifactData[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [activeTab, setActiveTab] = React.useState<"all" | "pending">("all");

  React.useEffect(() => {
    loadArtifacts();
  }, []);

  async function loadArtifacts() {
    try {
      setLoading(true);
      const data = await ApiClient.listArtifacts();
      setArtifacts(data);
    } catch (err) {
      console.error("Failed to load artifacts", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(artifactId: string) {
    try {
      await ApiClient.approveArtifact(artifactId);
      loadArtifacts();
    } catch (err: any) {
      alert(err.message || "Failed to approve");
    }
  }

  const pendingArtifacts = artifacts.filter(a => a.status === "PENDING_APPROVAL" || a.status === "DRAFT");
  const displayList = activeTab === "pending" ? pendingArtifacts : artifacts;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Tabs */}
      <div className="px-4 pt-3 pb-2 border-b border-gray-100 flex items-center space-x-1">
        <button
          onClick={() => setActiveTab("all")}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
            activeTab === "all" ? "bg-gray-100 text-gray-900" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          All Artifacts
        </button>
        <button
          onClick={() => setActiveTab("pending")}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center ${
            activeTab === "pending" ? "bg-amber-50 text-amber-700" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Approval Queue
          {pendingArtifacts.length > 0 && (
            <span className="ml-1.5 bg-amber-100 text-amber-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
              {pendingArtifacts.length}
            </span>
          )}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Loader2 className="h-6 w-6 animate-spin mb-2" />
            <p className="text-sm">Loading artifacts...</p>
          </div>
        ) : displayList.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <FileCode className="h-10 w-10 mb-3 opacity-40" />
            <p className="text-sm font-medium">
              {activeTab === "pending" ? "No pending approvals" : "No artifacts yet"}
            </p>
            <p className="text-xs mt-1 opacity-70">
              Artifacts are generated when agent tasks complete.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {displayList.map((art) => (
              <div
                key={art.id}
                className={`border rounded-xl p-4 transition-all hover:shadow-sm ${
                  art.status === "PENDING_APPROVAL" || art.status === "DRAFT"
                    ? "border-amber-200 bg-amber-50/50"
                    : art.status === "APPROVED"
                    ? "border-emerald-200 bg-emerald-50/30"
                    : "border-gray-200"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <FileText className="h-4 w-4 text-gray-500" />
                    <span className="font-medium text-sm text-gray-800">{art.title}</span>
                  </div>
                  <StatusBadge status={art.status} />
                </div>

                <div className="space-y-1.5 text-[11px] text-gray-500 pl-6">
                  <div className="flex items-center space-x-2">
                    <GitCommit className="h-3 w-3" />
                    <span>v{art.current_version} • {art.artifact_type}</span>
                  </div>
                  {art.versions?.[0]?.verification_verdict && (
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="h-3 w-3 text-emerald-500" />
                      <span>Verification: {art.versions[0].verification_verdict.status || "N/A"}</span>
                    </div>
                  )}
                  {art.versions?.[0]?.generating_model && (
                    <div className="flex items-center space-x-2">
                      <span>Model: {art.versions[0].generating_model}</span>
                    </div>
                  )}
                </div>

                {(art.status === "PENDING_APPROVAL" || art.status === "DRAFT") && (
                  <div className="mt-3 flex gap-2 pl-6">
                    <Button
                      size="sm"
                      className="h-7 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                      onClick={() => handleApprove(art.id)}
                    >
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs border-gray-300"
                    >
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "APPROVED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700">
          <CheckCircle className="w-3 h-3 mr-1" />
          Approved
        </span>
      );
    case "PENDING_APPROVAL":
    case "DRAFT":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-700 animate-pulse">
          <ShieldAlert className="w-3 h-3 mr-1" />
          Pending
        </span>
      );
    case "REJECTED":
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700">
          <XCircle className="w-3 h-3 mr-1" />
          Rejected
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600">
          {status}
        </span>
      );
  }
}
