"use client";

import * as React from "react";
import { Menu, ArrowRight, Shield, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

export function Topbar({ toggleSidebar }: { toggleSidebar: () => void }) {
  const [mode, setMode] = React.useState<{
    current_mode: string;
    banner_text: string;
    internet_status: string;
  } | null>(null);

  React.useEffect(() => {
    async function loadMode() {
      try {
        const data = await ApiClient.getSecurityMode();
        setMode(data);
      } catch {
        // Default to sovereign mode display on API failure
        setMode({
          current_mode: "SOVEREIGN",
          banner_text: "SOVEREIGN MODE — Internet: Blocked",
          internet_status: "blocked",
        });
      }
    }
    loadMode();
  }, []);



  const currentMode = mode?.current_mode || "sovereign";
  const isHybrid = currentMode === "hybrid";
  const isSovereign = currentMode === "sovereign";

  return (
    <header className="h-12 flex items-center justify-between px-4 sticky top-0 z-40 bg-white border-b border-gray-100">
      <div className="flex items-center space-x-3">
        <Button variant="ghost" size="icon" onClick={toggleSidebar} className="lg:hidden">
          <Menu className="h-5 w-5" />
        </Button>

        {/* FR9.6 — Persistent, unmissable sovereignty mode banner */}
        {mode && (
          <div className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide border ${
            isSovereign
              ? "bg-red-50 text-red-700 border-red-200"
              : isHybrid 
                ? "bg-purple-50 text-purple-700 border-purple-200"
                : "bg-amber-50 text-amber-700 border-amber-200"
          }`}>
            {isSovereign || isHybrid ? (
              <ShieldAlert className="h-3 w-3" />
            ) : (
              <Shield className="h-3 w-3" />
            )}
            <span>{mode.banner_text.split("—")[0].trim()}</span>
            <span className="text-[10px] opacity-70 ml-1">
              — {mode.banner_text.split("—")[1]?.trim()}
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-2">
        <button
          onClick={() => ApiClient.logout()}
          className="flex items-center px-3 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 text-gray-600 border border-gray-200 rounded-full transition-colors"
        >
          Sign Out
        </button>
      </div>
    </header>
  );
}
