"use client";

import { useCallback, useRef } from "react";
import { parseSSEEvent } from "@/lib/sse";
import { useChatStore } from "@/stores/chatStore";

/**
 * Hook for sending a chat message and streaming the SSE response.
 *
 * Connects to the backend chat endpoint via fetch + ReadableStream
 * (not EventSource — needed for POST with body and auth headers).
 */
export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);
  const {
    sessionId,
    startAssistantStream,
    appendToken,
    addCitation,
    setFollowUps,
    finishStream,
    failStream,
  } = useChatStore();

  const sendMessage = useCallback(
    async (message: string) => {
      if (!sessionId) return;

      // Abort any in-flight stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      startAssistantStream();

      const token = localStorage.getItem("auth_token") ?? "";

      try {
        const res = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ message }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          failStream(
            "I couldn’t get a response from the server. Please try again.",
          );
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (!data) continue;

            const event = parseSSEEvent(data);
            if (!event) continue;

            switch (event.type) {
              case "token":
                appendToken(event.token);
                break;
              case "citations":
                for (const c of event.citations) {
                  addCitation(c.title, c.source_url);
                }
                break;
              case "followups":
                setFollowUps(event.questions);
                break;
              case "error":
                failStream(event.message);
                return;
              case "done":
                finishStream();
                return;
            }
          }
        }

        // Stream ended without explicit "done" event
        finishStream();
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("SSE stream error:", err);
          failStream(
            "Something went wrong while streaming the response. Please try again.",
          );
        } else {
          finishStream();
        }
      }
    },
    [
      sessionId,
      startAssistantStream,
      appendToken,
      addCitation,
      setFollowUps,
      finishStream,
      failStream,
    ],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    finishStream();
  }, [finishStream]);

  return { sendMessage, cancel };
}
