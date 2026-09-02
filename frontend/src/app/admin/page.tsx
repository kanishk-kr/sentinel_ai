"use client";

import * as React from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Shield, ShieldAlert, Cpu, Network, Activity, Loader2, CheckCircle, XCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

export default function AdminPage() {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [securityData, setSecurityData] = React.useState<any>(null);
  const [models, setModels] = React.useState<any[]>([]);
  const [auditLog, setAuditLog] = React.useState<any[]>([]);
  const [chainVerification, setChainVerification] = React.useState<any>(null);
  const [networkStats, setNetworkStats] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    async function loadAdminData() {
      try {
        setLoading(true);
        const [security, modelList, audit, network] = await Promise.all([
          ApiClient.getSecurityMode().catch(() => null),
          ApiClient.listModels().catch(() => []),
          ApiClient.getAuditLog().catch(() => []),
          ApiClient.getNetworkMonitor().catch(() => null),
        ]);
        setSecurityData(security);
        setModels(modelList);
        setAuditLog(audit);
        setNetworkStats(network?.stats || null);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAdminData();
  }, []);

  async function handleVerifyChain() {
    try {
      const result = await ApiClient.verifyAuditChain();
      setChainVerification(result);
    } catch (err: any) {
      alert(err.message || "Verification failed");
    }
  }

  const isSovereign = securityData?.current_mode === "SOVEREIGN";

  return (
    <div className="flex h-screen overflow-hidden bg-white text-gray-900">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        <Topbar toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-auto p-4 md:p-6 lg:p-8 flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold tracking-tight text-gray-900">Admin Console</h1>
              <p className="text-sm text-gray-500 mt-0.5">System orchestration, security mode, and model registry.</p>
            </div>
            <Button 
              variant="outline" 
              className="border-red-200 text-red-600 hover:bg-red-50 text-xs"
              onClick={() => alert("Initiating Sovereign Lockdown... Disabling all external egress rules at the host firewall level (simulated).")}
            >
              <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
              Trigger Lockdown
            </Button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20 text-gray-400">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Sovereignty Control */}
              <div className={`rounded-xl p-5 border ${isSovereign ? 'border-red-200 bg-red-50/30' : 'border-emerald-200 bg-emerald-50/30'}`}>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold flex items-center text-gray-800">
                    <Shield className={`w-4 h-4 mr-2 ${isSovereign ? 'text-red-500' : 'text-emerald-500'}`} />
                    Sovereignty Mode
                  </h2>
                  <span className={`px-2.5 py-1 text-[10px] font-bold rounded-full border ${
                    isSovereign 
                      ? 'bg-red-100 text-red-700 border-red-200' 
                      : 'bg-emerald-100 text-emerald-700 border-emerald-200'
                  }`}>
                    {securityData?.current_mode || "UNKNOWN"}
                  </span>
                </div>
                
                <p className="text-xs text-gray-500 mb-4">
                  {securityData?.banner_text || "Checking system mode..."}
                </p>

                <div className="space-y-2.5">
                  <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200">
                    <div className="flex items-center">
                      <Network className="w-4 h-4 mr-2.5 text-gray-400" />
                      <div>
                        <p className="font-medium text-xs text-gray-700">Network Egress Monitor</p>
                        <p className="text-[10px] text-gray-400">
                          {networkStats ? `${networkStats.blocked_events} blocked, ${networkStats.allowed_events} allowed` : "Active and logging"}
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200">
                    <div className="flex items-center">
                      <Activity className="w-4 h-4 mr-2.5 text-gray-400" />
                      <div>
                        <p className="font-medium text-xs text-gray-700">Audit Chain Integrity</p>
                        {chainVerification ? (
                          <p className={`text-[10px] ${chainVerification.chain_integrity === 'PASS' ? 'text-emerald-500' : 'text-red-500'}`}>
                            {chainVerification.chain_integrity} — {chainVerification.entries_verified} entries verified
                          </p>
                        ) : (
                          <p className="text-[10px] text-gray-400">Click verify to check</p>
                        )}
                      </div>
                    </div>
                    <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={handleVerifyChain}>
                      Verify Now
                    </Button>
                  </div>
                </div>
              </div>

              {/* Model Registry — FR1.4 loaded from API */}
              <div className="rounded-xl p-5 border border-gray-200 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold flex items-center text-gray-800">
                    <Cpu className="w-4 h-4 mr-2 text-indigo-500" />
                    Model Registry (FR1.4)
                  </h2>
                  <span className="text-[10px] text-gray-400">{models.length} models</span>
                </div>

                <div className="flex-1 overflow-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="text-[10px] uppercase text-gray-400 border-b border-gray-100">
                      <tr>
                        <th className="px-3 py-2 font-medium">Model ID</th>
                        <th className="px-3 py-2 font-medium">Provider</th>
                        <th className="px-3 py-2 font-medium">State</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {models.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="px-3 py-6 text-center text-gray-400">
                            No models registered. Start the backend to load the manifest.
                          </td>
                        </tr>
                      ) : (
                        models.map((model: any) => (
                          <tr key={model.model_id} className="hover:bg-gray-50 transition-colors">
                            <td className="px-3 py-2.5 font-medium text-gray-700">{model.model_id}</td>
                            <td className="px-3 py-2.5 text-gray-500">{model.provider || model.display_name}</td>
                            <td className="px-3 py-2.5">
                              <span className={`text-[10px] font-semibold ${
                                model.state === 'AVAILABLE' || model.active
                                  ? 'text-emerald-600'
                                  : 'text-gray-400'
                              }`}>
                                {model.state || "UNKNOWN"}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Audit Log — Last 10 entries from API */}
              <div className="lg:col-span-2 rounded-xl p-5 border border-gray-200">
                <h2 className="text-sm font-semibold mb-3 text-gray-800">
                  Audit Log (FR7.6 — Hash-Chained, Sequence-Numbered)
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="text-[10px] uppercase text-gray-400 border-b border-gray-100">
                      <tr>
                        <th className="px-3 py-2 font-medium">Seq#</th>
                        <th className="px-3 py-2 font-medium">Type</th>
                        <th className="px-3 py-2 font-medium">Action</th>
                        <th className="px-3 py-2 font-medium">Allowed</th>
                        <th className="px-3 py-2 font-medium">Hash</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {auditLog.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-3 py-6 text-center text-gray-400">
                            No audit entries yet.
                          </td>
                        </tr>
                      ) : (
                        auditLog.slice(0, 15).map((entry: any) => (
                          <tr key={entry.id} className="hover:bg-gray-50">
                            <td className="px-3 py-2 font-mono text-gray-500">{entry.sequence_number}</td>
                            <td className="px-3 py-2 text-gray-600">{entry.entry_type}</td>
                            <td className="px-3 py-2 text-gray-600">{entry.action}</td>
                            <td className="px-3 py-2">
                              {entry.allowed ? (
                                <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                              ) : entry.allowed === false ? (
                                <XCircle className="h-3.5 w-3.5 text-red-500" />
                              ) : (
                                <span className="text-gray-300">—</span>
                              )}
                            </td>
                            <td className="px-3 py-2 font-mono text-[9px] text-gray-400 truncate max-w-[120px]">
                              {entry.entry_hash?.substring(0, 16)}...
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
