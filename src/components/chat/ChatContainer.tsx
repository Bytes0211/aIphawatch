"use client";

import { useCallback, useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useSSE } from "@/hooks/useSSE";
import { apiPost } from "@/lib/api";
import { CompanyContextBanner } from "./CompanyContextBanner";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";

interface ChatContainerProps {
  companyId: string;
  sessionId?: string | null;
  seedPrompt?: string | null;
  ticker?: string;
  companyName?: string;
}

/** Main chat interface: session management, message list, input, SSE streaming. */
export function ChatContainer({
  companyId,
  sessionId: initialSessionId = null,
  seedPrompt = null,
  ticker = "",
  companyName,
}: ChatContainerProps) {
  const {
    sessionId,
    messages,
    isStreaming,
    setSession,
    addUserMessage,
    reset,
  } = useChatStore();
  const { sendMessage } = useSSE();

  // Initialize or restore session
  useEffect(() => {
    if (initialSessionId) {
      setSession(initialSessionId, companyId);
    }
  }, [initialSessionId, companyId, setSession]);

  // Reset store when switching companies with no pre-existing session
  useEffect(() => {
    if (!initialSessionId) {
      reset();
    }
  }, [companyId, initialSessionId, reset]);

  // Create a new session if none exists
  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sessionId) return sessionId;

    try {
      const result = await apiPost<{ id: string }>("/chat/sessions", {
        company_id: companyId,
      });
      setSession(result.id, companyId);
      return result.id;
    } catch (err) {
      console.error("Failed to create chat session:", err);
      return null;
    }
  }, [sessionId, companyId, setSession]);

  // Send a message (creates session if needed)
  const handleSend = useCallback(
    async (message: string) => {
      const sid = await ensureSession();
      if (!sid) return;

      addUserMessage(message);

      // Small delay to let Zustand update propagate
      await new Promise((r) => setTimeout(r, 50));
      await sendMessage(message);
    },
    [ensureSession, addUserMessage, sendMessage],
  );

  // Handle follow-up chip clicks
  const handleFollowUp = useCallback(
    (question: string) => {
      handleSend(question);
    },
    [handleSend],
  );

  // Auto-send seed prompt on mount
  useEffect(() => {
    if (seedPrompt && !messages.length) {
      handleSend(seedPrompt);
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col rounded-lg border border-gray-200 bg-gray-50">
      {/* Company context banner */}
      {ticker && (
        <div className="p-3">
          <CompanyContextBanner ticker={ticker} companyName={companyName} />
        </div>
      )}

      {/* Message list */}
      <MessageList messages={messages} onFollowUp={handleFollowUp} />

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  );
}
