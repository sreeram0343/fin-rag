import { CitationCard } from "./CitationCard";
import type { CitationData } from "./CitationCard";

interface CitationPanelProps {
  citations: CitationData[];
  activeIndex?: number;
  onCitationClick?: (index: number, citation: CitationData) => void;
}

/**
 * Sidebar Panel containing coordinates citation cards mapping assertions in light theme.
 */
export const CitationPanel: React.FC<CitationPanelProps> = ({
  citations,
  activeIndex,
  onCitationClick,
}) => {
  return (
    <div className="flex flex-col h-full bg-slate-50 border-l border-slate-200 w-full shadow-sm">
      <div className="px-4 py-3.5 border-b border-slate-200/80 bg-white">
        <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
          Source Citations ({citations.length})
        </h3>
        <p className="text-[10px] text-slate-500 mt-0.5">
          Click any citation to view original coordinates context.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {citations.length === 0 ? (
          <div className="text-center py-10 text-slate-400 text-xs">
            No source references indexed for this answer.
          </div>
        ) : (
          citations.map((cit, idx) => (
            <CitationCard
              key={cit.chunk_id + "-" + idx}
              citation={cit}
              isActive={activeIndex === idx}
              onClick={() => onCitationClick?.(idx, cit)}
            />
          ))
        )}
      </div>
    </div>
  );
};
