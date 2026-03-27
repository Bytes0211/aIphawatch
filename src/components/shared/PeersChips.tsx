"use client";

interface PeersChipsProps {
  /** The primary company ticker (for context in the comparison prompt). */
  primaryTicker: string;
  /** List of 3-4 peer tickers to display as comparison chips. */
  peers: string[];
  /** Callback fired when a peer chip is clicked — seeds a comparison query. */
  onCompare: (prompt: string) => void;
}

/**
 * Peer ticker chips that pre-seed comparison queries in chat.
 *
 * Each chip generates a natural-language comparison prompt like
 * "Compare AAPL to MSFT on key financial metrics" when clicked.
 */
export function PeersChips({
  primaryTicker,
  peers,
  onCompare,
}: PeersChipsProps) {
  if (peers.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-gray-500">Compare with:</span>
      {peers.map((peer) => (
        <button
          key={peer}
          onClick={() =>
            onCompare(
              `Compare ${primaryTicker} to ${peer} on key financial metrics`
            )
          }
          className="rounded-full border border-gray-300 bg-white px-3 py-1 text-sm font-medium text-gray-700 hover:border-blue-400 hover:text-blue-600 transition-colors"
        >
          vs {peer}
        </button>
      ))}
    </div>
  );
}
