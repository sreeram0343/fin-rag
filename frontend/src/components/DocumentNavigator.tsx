import React from "react";

interface DocumentNavigatorProps {
  ticker: string;
  period: string;
  year: number;
  currentPage: number;
  totalPages: number;
  onPageSelect: (page: number) => void;
  documentId: string;
}

/**
 * Control panel providing filing period metadata, page jumps, and page lists in light theme.
 */
export const DocumentNavigator: React.FC<DocumentNavigatorProps> = ({
  ticker,
  period,
  year,
  currentPage,
  totalPages,
  onPageSelect,
  documentId,
}) => {
  const pagesArray = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    <div className="flex flex-col gap-3 p-4 bg-white border border-slate-200 rounded-xl shadow-sm text-slate-700">
      {/* File Period Info & page input */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs font-bold text-slate-800">
            {ticker} — {year} {period}
          </span>
          <span className="text-[10px] text-slate-500 font-mono px-2 py-0.5 bg-slate-50 border border-slate-200/60 rounded">
            ID: {documentId.substring(0, 8)}...
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-600">
          <span>Jump to Page</span>
          <input
            type="number"
            min={1}
            max={totalPages}
            value={currentPage}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              if (val >= 1 && val <= totalPages) {
                onPageSelect(val);
              }
            }}
            className="w-14 px-2 py-1 bg-slate-50 border border-slate-200 rounded text-center text-slate-800 focus:outline-none focus:border-blue-500 font-bold"
          />
          <span className="text-slate-400">/ {totalPages}</span>
        </div>
      </div>

      {/* Thumbnails Sidebar Navigation drawer list */}
      <div className="flex items-center gap-2 overflow-x-auto py-1 pt-2 border-t border-slate-100 custom-scrollbar scroll-smooth">
        {pagesArray.map((pageNum) => {
          const isSelected = pageNum === currentPage;
          const thumbUrl = `/api/v1/documents/${documentId}/thumbnail/${pageNum}`;

          return (
            <div
              key={pageNum}
              onClick={() => onPageSelect(pageNum)}
              className={`flex-shrink-0 cursor-pointer border rounded-lg overflow-hidden w-20 bg-slate-50 flex flex-col items-center hover:scale-[1.03] transition-all ${
                isSelected ? "border-red-500 ring-2 ring-red-100" : "border-slate-200"
              }`}
            >
              <div className="relative w-full h-20 overflow-hidden flex items-center justify-center bg-slate-100">
                <img
                  src={thumbUrl}
                  alt={`p${pageNum}`}
                  draggable={false}
                  className="object-cover max-h-full max-w-full"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
                <span className="absolute bottom-1 right-1 text-[9px] bg-black/60 px-1 py-0.5 rounded text-white font-mono font-bold">
                  {pageNum}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
