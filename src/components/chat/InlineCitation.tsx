"use client";

interface InlineCitationProps {
  citationRef: string;
  url: string;
}

/** Clickable citation badge linking to the source document. */
export function InlineCitation({ citationRef, url }: InlineCitationProps) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="mx-0.5 inline-flex items-center rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
      title={`Source: ${citationRef}`}
    >
      {citationRef}
    </a>
  );
}
