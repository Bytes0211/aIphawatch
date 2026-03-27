"use client";

interface FollowUpChipsProps {
  items: string[];
  onSelect: (question: string) => void;
}

/** Suggested follow-up questions rendered as clickable chips. */
export function FollowUpChips({ items, onSelect }: FollowUpChipsProps) {
  if (items.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map((item, i) => (
        <button
          key={i}
          onClick={() => onSelect(item)}
          className="rounded-full border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:border-blue-400 hover:text-blue-600 transition-colors"
        >
          {item}
        </button>
      ))}
    </div>
  );
}
