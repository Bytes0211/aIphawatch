"use client";

interface CompanyCardData {
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

interface CompanyCardProps {
  card: CompanyCardData;
  onSelect: (companyId: string) => void;
}

/** Dashboard card for a single watched company. */
export function CompanyCard({ card, onSelect }: CompanyCardProps) {
  const priceColor =
    card.price_change_pct && card.price_change_pct > 0
      ? "text-green-600"
      : card.price_change_pct && card.price_change_pct < 0
        ? "text-red-600"
        : "text-gray-600";

  const sentimentColor =
    card.sentiment_score && card.sentiment_score >= 30
      ? "bg-green-100 text-green-800"
      : card.sentiment_score && card.sentiment_score <= -30
        ? "bg-red-100 text-red-800"
        : "bg-gray-100 text-gray-700";

  const severityColor: Record<string, string> = {
    critical: "bg-red-600 text-white",
    high: "bg-red-100 text-red-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-gray-100 text-gray-600",
  };

  return (
    <button
      onClick={() => onSelect(card.company_id)}
      className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left hover:border-blue-300 hover:shadow-sm transition-all"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-lg font-bold text-gray-900">{card.ticker}</span>
          <span className="ml-2 text-sm text-gray-500">{card.name}</span>
        </div>
        {card.sector && (
          <span className="text-xs text-gray-400">{card.sector}</span>
        )}
      </div>

      {/* Metrics row */}
      <div className="mt-3 flex items-center gap-4 text-sm">
        {card.price != null && (
          <div>
            <span className="text-gray-500">Price </span>
            <span className="font-medium">${card.price.toFixed(2)}</span>
            {card.price_change_pct != null && (
              <span className={`ml-1 ${priceColor}`}>
                {card.price_change_pct > 0 ? "+" : ""}
                {card.price_change_pct.toFixed(1)}%
              </span>
            )}
          </div>
        )}

        {card.sentiment_score != null && (
          <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${sentimentColor}`}>
            Sentiment: {card.sentiment_score}
          </span>
        )}
      </div>

      {/* Activity indicators */}
      <div className="mt-2 flex items-center gap-3 text-xs">
        {card.new_filings_count > 0 && (
          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-blue-700">
            {card.new_filings_count} new filing{card.new_filings_count > 1 ? "s" : ""}
          </span>
        )}

        {card.risk_flag_count > 0 && card.risk_flag_max_severity && (
          <span className={`rounded px-1.5 py-0.5 ${severityColor[card.risk_flag_max_severity] ?? "bg-gray-100 text-gray-600"}`}>
            {card.risk_flag_count} risk flag{card.risk_flag_count > 1 ? "s" : ""}
          </span>
        )}

        {card.brief_id && (
          <span className="text-gray-400">Brief available</span>
        )}
      </div>
    </button>
  );
}
