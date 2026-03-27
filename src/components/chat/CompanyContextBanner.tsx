"use client";

interface CompanyContextBannerProps {
  ticker: string;
  companyName?: string;
}

/** Persistent banner showing the active company context. */
export function CompanyContextBanner({
  ticker,
  companyName,
}: CompanyContextBannerProps) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-800">
      <span className="font-semibold">{ticker}</span>
      {companyName && (
        <span className="text-blue-600">— {companyName}</span>
      )}
    </div>
  );
}
