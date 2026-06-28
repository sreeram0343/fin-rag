import React from "react";

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface BoundingBoxOverlayProps {
  bbox: BoundingBox;
  isActive?: boolean;
  onClick?: () => void;
  label?: string;
}

/**
 * Renders an interactive highlight box scaled dynamically to the parent document image canvas.
 */
export const BoundingBoxOverlay: React.FC<BoundingBoxOverlayProps> = ({
  bbox,
  isActive = false,
  onClick,
  label,
}) => {
  // Map normalized coordinates [0, 1000] to percentages
  const style: React.CSSProperties = {
    position: "absolute",
    left: `${bbox.x1 / 10}%`,
    top: `${bbox.y1 / 10}%`,
    width: `${(bbox.x2 - bbox.x1) / 10}%`,
    height: `${(bbox.y2 - bbox.y1) / 10}%`,
    border: isActive ? "2px solid rgba(239, 68, 68, 1)" : "1.5px solid rgba(59, 130, 246, 0.8)",
    backgroundColor: isActive ? "rgba(239, 68, 68, 0.15)" : "rgba(59, 130, 246, 0.1)",
    cursor: "pointer",
    transition: "all 0.15s ease-in-out",
    zIndex: isActive ? 20 : 10,
  };

  return (
    <div
      style={style}
      onClick={(e) => {
        e.stopPropagation();
        if (onClick) onClick();
      }}
      className={`group rounded-sm hover:border-red-500 hover:bg-red-500/10 ${
        isActive ? "ring-2 ring-red-500 ring-offset-1" : ""
      }`}
      title={label || "Source citation region"}
    >
      {label && (
        <span
          className="absolute -top-6 left-0 px-1.5 py-0.5 text-[10px] font-semibold text-white bg-blue-600 rounded shadow opacity-0 group-hover:opacity-100 transition-opacity duration-150 whitespace-nowrap z-30"
          style={{ backgroundColor: isActive ? "#ef4444" : "#2563eb" }}
        >
          {label}
        </span>
      )}
    </div>
  );
};
