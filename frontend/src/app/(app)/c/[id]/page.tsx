"use client";

import * as React from "react";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { useParams } from "next/navigation";

export default function ChatPage() {
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : null;

  return (
    <div className="flex-1 flex flex-col relative h-full">
      <ChatInterface sessionId={id} />
    </div>
  );
}
