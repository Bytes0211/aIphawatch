"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { WatchlistGrid } from "@/components/dashboard/WatchlistGrid";

interface DashboardData {
  cards: Array<{
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
  }>;
  as_of: string;
  time_range: string;
  total: number;
}

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("7d");

  useEffect(() => {
    setLoading(true);
    apiGet<DashboardData>(`/dashboard?time_range=${timeRange}`)
      .then(setData)
      .catch((err) => console.error("Dashboard load failed:", err))
      .finally(() => setLoading(false));
  }, [timeRange]);

  const handleSelect = (companyId: string) => {
    router.push(`/company/${companyId}/chat`);
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Watchlist</h2>
          <p className="text-sm text-gray-500">
            {data ? `${data.total} companies` : "Loading..."}
          </p>
        </div>

        {/* Time range selector */}
        <div className="flex gap-1 rounded-lg bg-gray-100 p-1">
          {["24h", "7d", "30d"].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                timeRange === range
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          Loading dashboard...
        </div>
      ) : data ? (
        <WatchlistGrid
          cards={data.cards}
          onSelectCompany={handleSelect}
        />
      ) : (
        <div className="text-center py-16 text-red-500">
          Failed to load dashboard.
        </div>
      )}
    </div>
  );
}
