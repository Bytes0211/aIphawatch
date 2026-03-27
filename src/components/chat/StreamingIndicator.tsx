"use client";

/** Animated typing dots shown while the assistant is streaming. */
export function StreamingIndicator() {
  return (
    <span className="inline-flex items-center gap-1 text-gray-400">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />
    </span>
  );
}
