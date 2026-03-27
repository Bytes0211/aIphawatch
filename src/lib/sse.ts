/**
 * SSE event types matching the backend chat streaming format:
 *   data: {"type": "token",     "content": "Apple's"}
 *   data: {"type": "citation",  "ref": "[10-K]", "url": "https://..."}
 *   data: {"type": "followups", "items": ["What drove...", "Compare to..."]}
 *   data: {"type": "done"}
 */

export interface SSETokenEvent {
  type: "token";
  content: string;
}

export interface SSECitationEvent {
  type: "citation";
  ref: string;
  url: string;
}

export interface SSEFollowupsEvent {
  type: "followups";
  items: string[];
}

export interface SSEDoneEvent {
  type: "done";
}

export type SSEEvent =
  | SSETokenEvent
  | SSECitationEvent
  | SSEFollowupsEvent
  | SSEDoneEvent;

/** Parse a raw SSE data line into a typed event. */
export function parseSSEEvent(data: string): SSEEvent | null {
  try {
    return JSON.parse(data) as SSEEvent;
  } catch {
    return null;
  }
}
