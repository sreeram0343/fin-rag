import { useState, useRef } from "react";
import { BoundingBoxOverlay } from "./BoundingBoxOverlay";
import type { BoundingBox } from "./BoundingBoxOverlay";

interface PDFViewerProps {
  documentId: string;
  currentPage: number;
  totalPages: number;
  activeBbox?: BoundingBox;
  bboxes?: Array<{ id: string; bbox: BoundingBox; label?: string }>;
  onBboxClick?: (id: string) => void;
  onPageChange?: (page: number) => void;
}

/**
 * Interactive PDF Page Canvas Viewer with zoom, pan, and coordinate overlay highlights in a white background theme.
 */
export const PDFViewer: React.FC<PDFViewerProps> = ({
  documentId,
  currentPage,
  totalPages,
  activeBbox,
  bboxes = [],
  onBboxClick,
  onPageChange,
}) => {
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStart = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const handleZoomIn = () => setZoom((z) => Math.min(2.5, z + 0.15));
  const handleZoomOut = () => setZoom((z) => Math.max(0.6, z - 0.15));
  const handleReset = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  const imageUrl = `/api/v1/documents/${documentId}/page/${currentPage}?resolution=150`;

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200/80 rounded-xl overflow-hidden shadow-sm">
      {/* Control Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200 text-slate-700">
        <div className="flex items-center gap-2">
          <button
            disabled={currentPage <= 1}
            onClick={() => onPageChange?.(currentPage - 1)}
            className="p-1.5 hover:bg-slate-200/60 rounded disabled:opacity-30 disabled:hover:bg-transparent"
          >
            ←
          </button>
          <span className="text-xs font-bold text-slate-700 font-mono">
            Page {currentPage} of {totalPages}
          </span>
          <button
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange?.(currentPage + 1)}
            className="p-1.5 hover:bg-slate-200/60 rounded disabled:opacity-30 disabled:hover:bg-transparent"
          >
            →
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-2">
          <button onClick={handleZoomOut} className="px-2.5 py-1 hover:bg-slate-200/60 rounded text-xs font-bold text-slate-600">-</button>
          <span className="text-[11px] font-bold text-slate-700 select-none">{Math.round(zoom * 100)}%</span>
          <button onClick={handleZoomIn} className="px-2.5 py-1 hover:bg-slate-200/60 rounded text-xs font-bold text-slate-600">+</button>
          <button onClick={handleReset} className="ml-2 text-xs text-blue-600 hover:underline font-semibold">Reset</button>
        </div>
      </div>

      {/* Page Canvas Container */}
      <div
        className="relative flex-1 overflow-hidden cursor-grab active:cursor-grabbing bg-slate-100/60 flex items-center justify-center p-4 min-h-[400px]"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.1s ease-out",
          }}
          className="relative select-none shadow-md border border-slate-200/50 bg-white"
        >
          <img
            src={imageUrl}
            alt={`Filing Page ${currentPage}`}
            draggable={false}
            className="max-h-[60vh] object-contain"
          />

          {/* Coordinate highlights overlay */}
          {bboxes.map((box) => (
            <BoundingBoxOverlay
              key={box.id}
              bbox={box.bbox}
              label={box.label}
              isActive={
                activeBbox &&
                activeBbox.x1 === box.bbox.x1 &&
                activeBbox.y1 === box.bbox.y1
              }
              onClick={() => onBboxClick?.(box.id)}
            />
          ))}

          {activeBbox && !bboxes.some((b) => b.bbox.x1 === activeBbox.x1) && (
            <BoundingBoxOverlay bbox={activeBbox} isActive={true} label="Selected Citation" />
          )}
        </div>
      </div>
    </div>
  );
};
