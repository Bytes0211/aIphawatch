"use client";

import { CompanyCard } from "./CompanyCard";

interface CardData {
  company_id: string;
  ticker: string;
  name: string;
  sector?: string | null;
  price?: number | null;
  price_change_pct?: number | null;
  sentiment_score?: number | null;
  risk_flag_count: number;
  risk_flag_max_severity?: string | null;
  new_filings_count: number;
  brief_id?: string | null;
  change_score: number;
}

interface WatchlistGridProps {
  cards: CardData[];
  onSelectCompany: (companyId: string) => void;
}

/** Grid layout of company cards for the dashboard. */
export function WatchlistGrid({ cards, onSelectCompany }: WatchlistGridProps) {
  if (cards.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
        No companies on your watchlist yet. Add a company to get started.
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => (
        <CompanyCard
          key={card.company_id}
          card={card}
          onSelect={onSelectCompany}
        />
      ))}
    </div>
  );
}
