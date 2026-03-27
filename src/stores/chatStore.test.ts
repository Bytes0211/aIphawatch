import { useChatStore } from "./chatStore";

// Reset store between tests
beforeEach(() => {
  useChatStore.getState().reset();
});

describe("chatStore", () => {
  it("starts with empty state", () => {
    const state = useChatStore.getState();
    expect(state.sessionId).toBeNull();
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
  });

  it("setSession sets session and company", () => {
    useChatStore.getState().setSession("s-1", "c-1");
    const state = useChatStore.getState();
    expect(state.sessionId).toBe("s-1");
    expect(state.companyId).toBe("c-1");
    expect(state.messages).toEqual([]);
  });

  it("addUserMessage appends a user message", () => {
    useChatStore.getState().addUserMessage("What are the risks?");
    const state = useChatStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].role).toBe("user");
    expect(state.messages[0].content).toBe("What are the risks?");
    expect(state.messages[0].isStreaming).toBe(false);
    expect(state.messages[0].id).toBeDefined();
  });

  it("startAssistantStream adds an empty streaming message", () => {
    useChatStore.getState().startAssistantStream();
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(true);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].role).toBe("assistant");
    expect(state.messages[0].content).toBe("");
    expect(state.messages[0].isStreaming).toBe(true);
  });

  it("appendToken accumulates content on streaming message", () => {
    useChatStore.getState().startAssistantStream();
    useChatStore.getState().appendToken("Hello ");
    useChatStore.getState().appendToken("world");
    const msg = useChatStore.getState().messages[0];
    expect(msg.content).toBe("Hello world");
  });

  it("addCitation appends to the last assistant message", () => {
    useChatStore.getState().startAssistantStream();
    useChatStore.getState().addCitation("Apple 10-K", "https://sec.gov");
    const msg = useChatStore.getState().messages[0];
    expect(msg.citations).toHaveLength(1);
    expect(msg.citations[0].ref).toBe("Apple 10-K");
  });

  it("setFollowUps sets follow-up questions", () => {
    useChatStore.getState().startAssistantStream();
    useChatStore.getState().setFollowUps(["Q1?", "Q2?"]);
    const msg = useChatStore.getState().messages[0];
    expect(msg.followUps).toEqual(["Q1?", "Q2?"]);
  });

  it("finishStream marks streaming complete", () => {
    useChatStore.getState().startAssistantStream();
    useChatStore.getState().appendToken("Done.");
    useChatStore.getState().finishStream();
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.messages[0].isStreaming).toBe(false);
    expect(state.messages[0].content).toBe("Done.");
  });

  it("failStream replaces empty placeholder with error text", () => {
    useChatStore.getState().startAssistantStream();
    useChatStore.getState().failStream("Server error");
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.messages[0].content).toBe("Server error");
    expect(state.messages[0].isStreaming).toBe(false);
  });

  it("reset clears all state", () => {
    useChatStore.getState().setSession("s-1", "c-1");
    useChatStore.getState().addUserMessage("test");
    useChatStore.getState().reset();
    const state = useChatStore.getState();
    expect(state.sessionId).toBeNull();
    expect(state.messages).toEqual([]);
  });

  it("full streaming lifecycle", () => {
    useChatStore.getState().setSession("s-1", "c-1");
    useChatStore.getState().addUserMessage("What are the key risks?");
    useChatStore.getState().startAssistantStream();
    useChatStore.getState().appendToken("Apple faces ");
    useChatStore.getState().appendToken("regulatory scrutiny.");
    useChatStore.getState().addCitation("10-K §Legal", "https://sec.gov/10k");
    useChatStore.getState().setFollowUps(["What is the timeline?", "How does it compare?"]);
    useChatStore.getState().finishStream();

    const state = useChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0].role).toBe("user");
    expect(state.messages[1].role).toBe("assistant");
    expect(state.messages[1].content).toBe("Apple faces regulatory scrutiny.");
    expect(state.messages[1].citations).toHaveLength(1);
    expect(state.messages[1].followUps).toHaveLength(2);
    expect(state.messages[1].isStreaming).toBe(false);
    expect(state.isStreaming).toBe(false);
  });
});
