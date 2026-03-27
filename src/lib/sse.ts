/**
 * SSE event types matching the backend chat streaming format:
 *   data: {"type": "token",      "token": "Apple's revenue..."}
 *   data: {"type": "citations",  "citations": [{"chunk_id": "...", ...}]}
 *   data: {"type": "followups",  "questions": ["What drove...", ...]}
 *   data: {"type": "done",       "session_id": "<uuid>"}
 *   data: {"type": "error",      "message": "An error occurred."}
 */

export interface SSETokenEvent {
  type: "token";
  token: string;
}

export interface SSECitationsEvent {
  type: "citations";
  citations: Array<{
    chunk_id: string;
    document_id: string;
    title: string;
    source_type: string;
    source_url: string;
    excerpt: string;
  }>;
}

export interface SSEFollowupsEvent {
  type: "followups";
  questions: string[];
}

export interface SSEDoneEvent {
  type: "done";
  session_id: string;
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | SSETokenEvent
  | SSECitationsEvent
  | SSEFollowupsEvent
  | SSEDoneEvent
  | SSEErrorEvent;

/** Parse a raw SSE data line into a typed event. */
export function parseSSEEvent(data: string): SSEEvent | null {
  try {
    return JSON.parse(data) as SSEEvent;
  } catch {
    return null;
  }
}
