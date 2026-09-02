"use client";

import * as React from "react";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function Home() {
  return (
    <div className="flex-1 flex flex-col relative h-full">
      <ChatInterface sessionId={null} />
    </div>
  );
}
