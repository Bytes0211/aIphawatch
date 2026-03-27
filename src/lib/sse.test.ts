import { parseSSEEvent, type SSEEvent } from "./sse";

describe("parseSSEEvent", () => {
  it("parses a token event", () => {
    const event = parseSSEEvent('{"type":"token","token":"Hello world"}');
    expect(event).toEqual({ type: "token", token: "Hello world" });
  });

  it("parses a citations event", () => {
    const raw = JSON.stringify({
      type: "citations",
      citations: [
        {
          chunk_id: "c1",
          document_id: "d1",
          title: "Apple 10-K",
          source_type: "edgar_10k",
          source_url: "https://sec.gov/test",
          excerpt: "Revenue grew 12%",
        },
      ],
    });
    const event = parseSSEEvent(raw) as Extract<SSEEvent, { type: "citations" }>;
    expect(event.type).toBe("citations");
    expect(event.citations).toHaveLength(1);
    expect(event.citations[0].title).toBe("Apple 10-K");
  });

  it("parses a followups event", () => {
    const raw = JSON.stringify({
      type: "followups",
      questions: ["What drove growth?", "Compare margins"],
    });
    const event = parseSSEEvent(raw) as Extract<SSEEvent, { type: "followups" }>;
    expect(event.type).toBe("followups");
    expect(event.questions).toEqual(["What drove growth?", "Compare margins"]);
  });

  it("parses a done event", () => {
    const event = parseSSEEvent('{"type":"done","session_id":"abc-123"}');
    expect(event).toEqual({ type: "done", session_id: "abc-123" });
  });

  it("parses an error event", () => {
    const event = parseSSEEvent('{"type":"error","message":"Something failed"}');
    expect(event).toEqual({ type: "error", message: "Something failed" });
  });

  it("returns null for invalid JSON", () => {
    expect(parseSSEEvent("not json")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(parseSSEEvent("")).toBeNull();
  });
});
