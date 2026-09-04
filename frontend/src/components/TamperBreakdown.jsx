import React, { useState } from 'react';
import { ShieldAlert, Cpu, Flame, FileText, Binary, ChevronDown, ChevronUp, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function TamperBreakdown({ tamperRiskScore, signals, triggeredSignals }) {
  const [expanded, setExpanded] = useState(true);

  if (tamperRiskScore === undefined || !signals) return null;

  const getRiskColor = (score) => {
    if (score >= 30) return { text: 'text-rose-400', border: 'border-rose-500', bg: 'bg-rose-500', pill: 'bg-rose-950 text-rose-300 border-rose-800' };
    if (score >= 15) return { text: 'text-amber-400', border: 'border-amber-500', bg: 'bg-amber-500', pill: 'bg-amber-950 text-amber-300 border-amber-800' };
    return { text: 'text-emerald-400', border: 'border-emerald-500', bg: 'bg-emerald-500', pill: 'bg-emerald-950 text-emerald-300 border-emerald-800' };
  };

  const riskColor = getRiskColor(tamperRiskScore);

  const cnn = signals.cnn_model || {};
  const ela = signals.error_level_analysis || {};
  const exif = signals.exif_forensics || {};
  const mrz = signals.mrz_checksum || {};

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Tamper & Forgery Risk Assessment</h3>
            <p className="text-xs text-slate-400">Ensemble of CNN Inpainting Model + Classical Forensics</p>
          </div>
        </div>

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-slate-400 hover:text-white p-1 rounded-md transition-colors"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Gauge and Composite Score Bar */}
      <div className="my-5 flex flex-col sm:flex-row items-center justify-between gap-6 p-4 rounded-xl bg-slate-950/60 border border-slate-800">
        <div className="flex items-center space-x-4">
          <div className="relative w-20 h-20 flex items-center justify-center">
            {/* SVG Radial Gauge */}
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-slate-800"
                strokeWidth="3.5"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={riskColor.text}
                strokeDasharray={`${tamperRiskScore}, 100`}
                strokeWidth="3.5"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center">
              <span className={`text-xl font-black font-mono tracking-tighter ${riskColor.text}`}>
                {tamperRiskScore}
              </span>
              <span className="text-[9px] text-slate-400 -mt-1 uppercase">/ 100</span>
            </div>
          </div>

          <div>
            <div className="flex items-center space-x-2">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border uppercase tracking-wider ${riskColor.pill}`}>
                {tamperRiskScore >= 65 ? "High Tamper Risk" : tamperRiskScore >= 30 ? "Moderate Risk" : "Low Risk Authenticity"}
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-1.5 max-w-xs">
              {tamperRiskScore >= 65
                ? "Multiple independent forensic signals flagged potential photo replacement, text modification, or checksum mismatch."
                : tamperRiskScore >= 30
                ? "Subtle compression or metadata anomalies detected. Recommend manual visual review."
                : "No significant convolutional, compression, or format forgery signals identified."}
            </p>
          </div>
        </div>

        {/* Triggered Signals Summary Badge */}
        {triggeredSignals && triggeredSignals.length > 0 ? (
          <div className="w-full sm:w-auto p-3 rounded-lg bg-rose-950/40 border border-rose-900/60 text-rose-300 text-xs">
            <span className="font-semibold block mb-1 flex items-center text-rose-200">
              <AlertCircle className="w-3.5 h-3.5 mr-1 text-rose-400" />
              {triggeredSignals.length} Signal(s) Triggered:
            </span>
            <ul className="list-disc list-inside space-y-0.5 text-[11px] text-rose-300/90">
              {triggeredSignals.map((sig, idx) => (
                <li key={idx}>{sig}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="flex items-center space-x-2 text-xs text-emerald-400 font-medium px-3 py-2 bg-emerald-950/30 rounded-lg border border-emerald-900/50">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>All 4 Forensic Sub-Systems Clear</span>
          </div>
        )}
      </div>

      {/* Expandable 4-Signal Breakdown */}
      {expanded && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 pt-4 border-t border-slate-800 text-xs">
          {/* 1. ONNX CNN Model */}
          <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-white flex items-center">
                <Cpu className="w-3.5 h-3.5 mr-1.5 text-sky-400" />
                1. ONNX CNN Classifier
              </span>
              <span className="font-mono text-sky-400 font-bold">
                {cnn.score !== undefined ? `${cnn.score}%` : 'N/A'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              MobileNetV3 trained on MIDV + synthetic photo splicing. Weight: 35%.
            </p>
            <div className="mt-2 text-[10px] text-slate-400 font-mono">
              Status: <span className="text-slate-300">{cnn.status || 'Active'}</span>
            </div>
          </div>

          {/* 2. Error Level Analysis */}
          <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-white flex items-center">
                <Flame className="w-3.5 h-3.5 mr-1.5 text-amber-400" />
                2. Error Level Analysis (ELA)
              </span>
              <span className="font-mono text-amber-400 font-bold">
                {ela.score !== undefined ? `${ela.score}` : 'N/A'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Measures 90% JPEG re-compression difference across document zones. Weight: 25%.
            </p>
            <div className="mt-2 text-[10px] text-slate-400">
              {ela.detail || "Compression uniformity normal"}
            </div>
          </div>

          {/* 3. EXIF Forensics */}
          <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-white flex items-center">
                <FileText className="w-3.5 h-3.5 mr-1.5 text-indigo-400" />
                3. EXIF Metadata Forensics
              </span>
              <span className="font-mono text-indigo-400 font-bold">
                {exif.score !== undefined ? `${exif.score}%` : 'N/A'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Checks for Photoshop/GIMP editing tags & timestamp discordance. Weight: 15%.
            </p>
            <div className="mt-2 text-[10px] text-slate-300">
              {exif.software_detected ? (
                <span className="text-rose-400 font-medium">Software: {exif.software_detected}</span>
              ) : (
                <span className="text-slate-400">No graphic editor signatures detected</span>
              )}
            </div>
          </div>

          {/* 4. MRZ Checksum */}
          <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-white flex items-center">
                <Binary className="w-3.5 h-3.5 mr-1.5 text-emerald-400" />
                4. MRZ Checksum Signal
              </span>
              <span className={`font-mono font-bold ${mrz.checksum_valid ? 'text-emerald-400' : 'text-rose-400'}`}>
                {mrz.checksum_valid ? 'VALID (0)' : 'FAILED (+95)'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              ICAO Doc 9303 7-3-1 check digit validation. Weight: 25%.
            </p>
            <div className="mt-2 text-[10px]">
              {mrz.checksum_valid ? (
                <span className="text-emerald-400">All mathematical check digits match</span>
              ) : (
                <span className="text-rose-400 font-medium">Mathematical tamper signal active</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
