"use client";

import { ChatContainer } from "@/components/chat/ChatContainer";

interface ChatPageProps {
  params: { id: string };
}

export default function ChatPage({ params }: ChatPageProps) {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <ChatContainer companyId={params.id} />
    </div>
  );
}
