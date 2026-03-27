"use client";

import type { ChatMessage } from "@/stores/chatStore";
import { InlineCitation } from "./InlineCitation";
import { StreamingIndicator } from "./StreamingIndicator";
import { FollowUpChips } from "./FollowUpChips";

interface MessageBubbleProps {
  message: ChatMessage;
  onFollowUp?: (question: string) => void;
}

/** Renders a single chat message with role-based styling. */
export function MessageBubble({ message, onFollowUp }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-white text-gray-800 border border-gray-200"
        }`}
      >
        {/* Message content */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
          {message.isStreaming && !message.content && <StreamingIndicator />}
        </div>

        {/* Citations */}
        {message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.map((c) => (
              <InlineCitation
                key={`${c.ref}-${c.url}`}
                citationRef={c.ref}
                url={c.url}
              />
            ))}
          </div>
        )}

        {/* Follow-up chips (only on completed assistant messages) */}
        {!isUser &&
          !message.isStreaming &&
          message.followUps.length > 0 &&
          onFollowUp && (
            <FollowUpChips items={message.followUps} onSelect={onFollowUp} />
          )}
      </div>
    </div>
  );
}
