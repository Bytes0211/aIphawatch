"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/stores/chatStore";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
  onFollowUp: (question: string) => void;
}

/** Scrollable message thread with auto-scroll to bottom. */
export function MessageList({ messages, onFollowUp }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages or streaming tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400 text-sm">
        Start a conversation about this company...
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onFollowUp={onFollowUp} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
