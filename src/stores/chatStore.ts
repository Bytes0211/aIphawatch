import { create } from "zustand";

/** Citation reference from an assistant response. */
export interface Citation {
  ref: string;
  url: string;
}

/** A single chat message (user or assistant). */
export interface ChatMessage {
  /** Stable unique ID for React keys/diffing. */
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  followUps: string[];
  isStreaming: boolean;
}

interface ChatState {
  /** Current chat session ID (null = no session yet). */
  sessionId: string | null;
  /** All messages in the current session. */
  messages: ChatMessage[];
  /** Whether an SSE stream is currently active. */
  isStreaming: boolean;
  /** Company ID for the active chat. */
  companyId: string | null;

  /** Set the active session. */
  setSession: (sessionId: string, companyId: string) => void;
  /** Add a complete user message. */
  addUserMessage: (content: string) => void;
  /** Start a new streaming assistant response. */
  startAssistantStream: () => void;
  /** Append a token to the current streaming message. */
  appendToken: (token: string) => void;
  /** Add a citation to the current streaming message. */
  addCitation: (ref: string, url: string) => void;
  /** Set follow-up suggestions on the current message. */
  setFollowUps: (items: string[]) => void;
  /** Mark the current stream as complete. */
  finishStream: () => void;
  /**
   * Mark the current stream as failed.
   * Replaces an empty assistant placeholder with an error message,
   * or appends a new assistant error message if no placeholder exists.
   */
  failStream: (errorText: string) => void;
  /** Reset chat state for a new session. */
  reset: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  isStreaming: false,
  companyId: null,

  setSession: (sessionId, companyId) =>
    set({ sessionId, companyId, messages: [], isStreaming: false }),

  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: crypto.randomUUID(),
          role: "user",
          content,
          citations: [],
          followUps: [],
          isStreaming: false,
        },
      ],
    })),

  startAssistantStream: () =>
    set((state) => ({
      isStreaming: true,
      messages: [
        ...state.messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "",
          citations: [],
          followUps: [],
          isStreaming: true,
        },
      ],
    })),

  appendToken: (token) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant" && last.isStreaming) {
        msgs[msgs.length - 1] = { ...last, content: last.content + token };
      }
      return { messages: msgs };
    }),

  addCitation: (ref, url) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = {
          ...last,
          citations: [...last.citations, { ref, url }],
        };
      }
      return { messages: msgs };
    }),

  setFollowUps: (items) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, followUps: items };
      }
      return { messages: msgs };
    }),

  finishStream: () =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant" && last.isStreaming) {
        msgs[msgs.length - 1] = { ...last, isStreaming: false };
      }
      return { messages: msgs, isStreaming: false };
    }),

  failStream: (errorText) =>
    set((state) => {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];

      if (
        last?.role === "assistant" &&
        last.isStreaming &&
        (!last.content || last.content.trim() === "")
      ) {
        msgs[msgs.length - 1] = {
          ...last,
          content: errorText,
          isStreaming: false,
        };
      } else {
        msgs.push({
          id: crypto.randomUUID(),
          role: "assistant",
          content: errorText,
          citations: [],
          followUps: [],
          isStreaming: false,
        });
      }

      return { messages: msgs, isStreaming: false };
    }),

  reset: () =>
    set({ sessionId: null, messages: [], isStreaming: false, companyId: null }),
}));
