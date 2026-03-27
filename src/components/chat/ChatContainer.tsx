"use client";

import { useCallback, useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chatStore";
import type { BackendMessage } from "@/stores/chatStore";
import { useSSE } from "@/hooks/useSSE";
import { apiGet, apiPost } from "@/lib/api";
import { CompanyContextBanner } from "./CompanyContextBanner";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";

interface ChatContainerProps {
  companyId: string;
  ticker: string;
  sessionId?: string | null;
  seedPrompt?: string | null;
  companyName?: string;
}

/** Main chat interface: session management, message list, input, SSE streaming. */
export function ChatContainer({
  companyId,
  ticker,
  sessionId: initialSessionId = null,
  seedPrompt = null,
  companyName,
}: ChatContainerProps) {
  const sentSeedRef = useRef<string | null>(null);

  const {
    sessionId,
    messages,
    isStreaming,
    setSession,
    loadMessages,
    addUserMessage,
    reset,
  } = useChatStore();
  const { sendMessage } = useSSE();

  // Initialize or restore session
  useEffect(() => {
    if (initialSessionId) {
      setSession(initialSessionId, companyId);
      // Rehydrate message history from the server
      apiGet<{ messages: BackendMessage[] }>(
        `/chat/sessions/${initialSessionId}/messages`,
      )
        .then((data) => loadMessages(data.messages))
        .catch((err) => console.error("Failed to load message history:", err));
    }
  }, [initialSessionId, companyId, setSession, loadMessages]);

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
        ticker,
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

  // Auto-send seed prompt whenever it changes (e.g., from a PeersChip click)
  useEffect(() => {
    if (seedPrompt && seedPrompt !== sentSeedRef.current) {
      sentSeedRef.current = seedPrompt;
      handleSend(seedPrompt);
    }
  }, [seedPrompt, handleSend]);

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
