import type { BoundingBox } from "./BoundingBoxOverlay";

export interface CitationData {
  chunk_id: string;
  document_id: string;
  page: number;
  bbox: BoundingBox;
  section?: string;
  ticker: string;
  period: string;
  confidence: {
    similarity_score: number;
    reranker_score?: number;
    verification_status: "verified" | "unverified";
  };
}

interface CitationCardProps {
  citation: CitationData;
  isActive?: boolean;
  onClick?: () => void;
}

/**
 * Display card for detailed coordinate citations in a clean white-mode dashboard.
 */
export const CitationCard: React.FC<CitationCardProps> = ({
  citation,
  isActive = false,
  onClick,
}) => {
  const { ticker, period, page, section, confidence } = citation;

  return (
    <div
      onClick={onClick}
      className={`p-3.5 rounded-xl cursor-pointer border shadow-sm transition-all hover:shadow-md hover:border-slate-400 flex flex-col gap-2 ${
        isActive
          ? "border-red-500 bg-red-50/20"
          : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
          {ticker} ({period})
        </span>
        <span className="text-[11px] font-semibold text-slate-500">
          Page {page}
        </span>
      </div>

      <div className="flex flex-col text-slate-700">
        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Section</span>
        <span className="text-xs font-bold text-slate-800 line-clamp-1">{section || "Unspecified Section"}</span>
      </div>

      {/* Metrics Row */}
      <div className="flex items-center gap-3 mt-1.5 pt-2 border-t border-slate-100 text-[10px] text-slate-500 font-semibold">
        <div className="flex flex-col">
          <span>Dense Cosine</span>
          <span className="text-slate-800 font-bold">{confidence.similarity_score.toFixed(3)}</span>
        </div>
        {confidence.reranker_score !== undefined && (
          <div className="flex flex-col">
            <span>Rerank Score</span>
            <span className="text-slate-800 font-bold">{confidence.reranker_score.toFixed(3)}</span>
          </div>
        )}
        <div className="ml-auto flex items-center">
          {confidence.verification_status === "verified" ? (
            <span className="px-1.5 py-0.5 rounded-full text-[9px] bg-green-50 text-green-700 border border-green-200 flex items-center gap-0.5 font-bold">
              ✓ Verified
            </span>
          ) : (
            <span className="px-1.5 py-0.5 rounded-full text-[9px] bg-yellow-50 text-yellow-700 border border-yellow-200 font-bold">
              Unverified
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
