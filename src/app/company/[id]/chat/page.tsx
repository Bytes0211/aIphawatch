"use client";

import { useEffect, useRef, useState } from "react";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { PeersChips } from "@/components/shared/PeersChips";
import { apiGet } from "@/lib/api";

interface ChatPageProps {
  params: { id: string };
}

interface CompanyInfo {
  id: string;
  ticker: string;
  name: string;
  sector?: string;
}

// Fallback peers — used only until company metadata API provides real peers
const DEFAULT_PEERS = ["MSFT", "GOOG", "AMZN"];

export default function ChatPage({ params }: ChatPageProps) {
  const [company, setCompany] = useState<CompanyInfo | null>(null);
  const seedRef = useRef<string | null>(null);

  // Fetch company info to get the real ticker
  useEffect(() => {
    apiGet<CompanyInfo>(`/companies/${params.id}`)
      .then(setCompany)
      .catch((err) => console.error("Failed to load company:", err));
  }, [params.id]);

  const handleCompare = (prompt: string) => {
    // Set seed prompt — ChatContainer will pick it up and send it
    seedRef.current = prompt;
    // Force re-render so ChatContainer sees the new seedPrompt
    setCompany((c) => (c ? { ...c } : c));
  };

  const ticker = company?.ticker ?? params.id;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 space-y-4">
      <PeersChips
        primaryTicker={ticker}
        peers={DEFAULT_PEERS}
        onCompare={handleCompare}
      />
      <ChatContainer
        companyId={params.id}
        ticker={ticker}
        companyName={company?.name}
        seedPrompt={seedRef.current}
      />
    </div>
  );
}
