import type { CitationData } from "./CitationCard";

interface AnswerViewerProps {
  answer: string;
  citations: CitationData[];
  activeCitationIndex?: number;
  onCitationClick?: (index: number, citation: CitationData) => void;
}

/**
 * Renders the synthesized RAG report with interactive superscript badges for coordinate citations in light theme.
 */
export const AnswerViewer: React.FC<AnswerViewerProps> = ({
  answer,
  citations,
  activeCitationIndex,
  onCitationClick,
}) => {
  const renderFormattedText = () => {
    const regex = /(\[\d+\]|\[Chunk \d+\])/g;
    const parts = answer.split(regex);

    if (parts.length <= 1) {
      return <p className="text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">{answer}</p>;
    }

    return (
      <p className="text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">
        {parts.map((part, index) => {
          const match = part.match(/\[(?:Chunk )?(\d+)\]/);
          if (match) {
            const citationNum = parseInt(match[1], 10);
            const citationIndex = citationNum - 1;

            if (citationIndex >= 0 && citationIndex < citations.length) {
              const citation = citations[citationIndex];
              const isActive = activeCitationIndex === citationIndex;

              return (
                <button
                  key={index}
                  onClick={() => onCitationClick?.(citationIndex, citation)}
                  className={`inline-flex items-center justify-center align-super mx-0.5 px-1.5 py-0.5 text-[9px] font-bold rounded-full transition-colors ${isActive
                      ? "bg-red-500 text-white shadow-sm ring-1 ring-red-400"
                      : "bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200/50"
                    }`}
                  title={`View Source Page ${citation.page}: ${citation.section || ""}`}
                >
                  {citationNum}
                </button>
              );
            }
          }
          return <span key={index}>{part}</span>;
        })}
      </p>
    );
  };

  return (
    <div className="p-5 rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
          Verified Analysis Report
        </h4>
        <span className="text-[10px] text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full font-bold">          ✓ Math Audited
        </span>
      </div>

      <div className="py-1">
        {renderFormattedText()}
      </div>
    </div>
  );
};
