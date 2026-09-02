"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Shield, Lock, User, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    
    try {
      await ApiClient.login({ username, password });
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Failed to authenticate");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f9fafb] relative">
      <div className="bg-white p-8 rounded-2xl w-full max-w-md border border-gray-200 shadow-lg">
        <div className="flex flex-col items-center mb-8">
          <div className="h-14 w-14 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4">
            <Shield className="h-7 w-7 text-indigo-600" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">SENTINEL</h1>
          <p className="text-xs text-gray-400 mt-1 font-medium tracking-wide uppercase">Sovereign AI Workbench</p>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-xs flex items-center">
            <AlertTriangle className="h-3.5 w-3.5 mr-2 flex-shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-500">Username</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-gray-50 border border-gray-200 rounded-lg py-2.5 pl-10 pr-4 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all"
                placeholder="admin"
                required
              />
            </div>
          </div>
          
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-500">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-gray-50 border border-gray-200 rounded-lg py-2.5 pl-10 pr-4 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all"
                placeholder="••••••••"
                required
              />
            </div>
          </div>

          <Button type="submit" className="w-full mt-4 h-10 bg-indigo-600 hover:bg-indigo-700 text-white" disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {loading ? "Authenticating..." : "Sign In"}
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-gray-100 text-center">
          <p className="text-[10px] text-gray-400">
            Demo accounts: admin / engineer / analyst / viewer (password: [role]123)
          </p>
        </div>
      </div>
    </div>
  );
}
