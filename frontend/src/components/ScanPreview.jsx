import React, { useState } from 'react';
import { Crop, CheckCircle, AlertTriangle, Eye, Flame, Layers } from 'lucide-react';

export default function ScanPreview({ scanMetadata, elaHeatmapBase64 }) {
  const [showHeatmap, setShowHeatmap] = useState(false);

  if (!scanMetadata) return null;

  const {
    contour_detected,
    aspect_ratio,
    dimensions,
    preview_original_base64,
    preview_cropped_base64
  } = scanMetadata;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center">
            <Crop className="w-4 h-4 mr-2 text-sky-400" />
            Module 1: Auto-Scan & Perspective Correction Preview
          </h3>
          <p className="text-xs text-slate-400">
            Confirms edge alignment, deskew angle, and glare equalization before OCR
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {scanMetadata.crop_method && (
            <span className="px-2.5 py-1 rounded-md bg-sky-950 border border-sky-800 text-sky-300 text-xs font-mono font-medium">
              Method: {scanMetadata.crop_method}
            </span>
          )}

          {contour_detected ? (
            <span className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-emerald-950/80 border border-emerald-800 text-emerald-400 text-xs font-medium">
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Contour Locked (~{aspect_ratio}:1)</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-amber-950/80 border border-amber-800 text-amber-400 text-xs font-medium">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Aspect Normalization</span>
            </span>
          )}

          {elaHeatmapBase64 && (
            <button
              onClick={() => setShowHeatmap(!showHeatmap)}
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                showHeatmap
                  ? "bg-rose-950 border-rose-700 text-rose-300"
                  : "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700"
              }`}
            >
              <Flame className={`w-3.5 h-3.5 ${showHeatmap ? "text-rose-400" : "text-amber-400"}`} />
              <span>{showHeatmap ? "Hide ELA Heatmap" : "View ELA Heatmap"}</span>
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Original Image */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col items-center">
          <div className="w-full flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="font-semibold uppercase tracking-wider text-[11px] flex items-center">
              <Layers className="w-3 h-3 mr-1 text-slate-500" />
              Input Capture (Raw Angle)
            </span>
            <span className="text-[11px]">Original Frame</span>
          </div>
          <div className="w-full h-56 bg-slate-900 rounded-lg flex items-center justify-center overflow-hidden border border-slate-800">
            {preview_original_base64 ? (
              <img
                src={preview_original_base64}
                alt="Original Upload"
                className="max-h-full max-w-full object-contain"
              />
            ) : (
              <span className="text-xs text-slate-500">No original preview</span>
            )}
          </div>
        </div>

        {/* Deskewed Scan or ELA Heatmap */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col items-center relative">
          <div className="w-full flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="font-semibold uppercase tracking-wider text-[11px] flex items-center">
              <Eye className="w-3 h-3 mr-1 text-sky-400" />
              {showHeatmap ? "Error Level Analysis Heatmap" : "Deskewed Bio-Page Scan (1420x1000)"}
            </span>
            <span className="text-[11px] text-sky-400 font-mono">
              {dimensions ? `${dimensions.width}×${dimensions.height}px` : "Standard TD3"}
            </span>
          </div>

          <div className="w-full h-56 bg-slate-900 rounded-lg flex items-center justify-center overflow-hidden border border-slate-800 relative">
            {showHeatmap && elaHeatmapBase64 ? (
              <div className="relative w-full h-full flex items-center justify-center">
                <img
                  src={elaHeatmapBase64}
                  alt="ELA Heatmap"
                  className="max-h-full max-w-full object-contain"
                />
                <div className="absolute bottom-1.5 right-1.5 px-2 py-0.5 rounded bg-slate-950/80 text-[10px] text-rose-300 border border-rose-900/60 font-mono">
                  Bright spots = Compression disparity
                </div>
              </div>
            ) : preview_cropped_base64 ? (
              <img
                src={preview_cropped_base64}
                alt="Deskewed Passport Scan"
                className="max-h-full max-w-full object-contain"
              />
            ) : (
              <span className="text-xs text-slate-500">No processed scan</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
