import React from 'react';
import { UserCheck, UserX, AlertTriangle, ShieldAlert, CheckCircle2, ScanFace, Eye, Camera } from 'lucide-react';

export default function FaceMatchCard({ faceMatch }) {
  if (!faceMatch) return null;

  const {
    performed,
    passport_face_detected,
    detection_method,
    bounding_box,
    live_face_detected,
    match_score,
    is_match,
    engine,
    passport_face_preview_base64,
    live_face_preview_base64,
    photo_determination,
    liveness_limitation_note,
    summary,
    message
  } = faceMatch;

  const photoDet = photo_determination || {};
  const icao = photoDet.icao_compliance || {};
  const isPhotoFlagged = photoDet.is_flagged || false;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
      {/* Card Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
            <ScanFace className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Module 5: Photo Determination & Biometrics</h3>
            <p className="text-xs text-slate-400">Portrait Localization, Splice Forensics & 1:1 Face Match</p>
          </div>
        </div>

        <span
          className={`px-2.5 py-0.5 rounded-full text-xs font-bold border font-mono ${
            isPhotoFlagged
              ? "bg-rose-950 text-rose-300 border-rose-800"
              : "bg-emerald-950 text-emerald-300 border-emerald-800"
          }`}
        >
          {isPhotoFlagged ? "PHOTO TAMPER FLAG" : "PHOTO AUTHENTIC"}
        </span>
      </div>

      {/* 1. Photo Determination & Splice Forensics Grid */}
      <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            {/* Passport Portrait Crop Frame */}
            <div className="w-24 h-32 rounded-lg bg-slate-900 border-2 border-indigo-500/40 overflow-hidden flex items-center justify-center flex-shrink-0 shadow-md relative">
              {passport_face_preview_base64 ? (
                <img
                  src={passport_face_preview_base64}
                  alt="Extracted Passport Portrait"
                  className="w-full h-full object-cover"
                />
              ) : (
                <UserX className="w-8 h-8 text-slate-600" />
              )}
              <div className="absolute bottom-0 inset-x-0 bg-slate-950/80 text-[9px] text-center text-slate-300 py-0.5 font-mono">
                {bounding_box ? `${bounding_box.width}×${bounding_box.height}px` : 'ICAO'}
              </div>
            </div>

            <div>
              <span className="text-[10px] font-mono text-sky-400 uppercase tracking-wider block">
                {detection_method || "dlib HOG Deep Neural Detector"}
              </span>
              <h4 className="text-sm font-bold text-white mt-0.5">
                {photoDet.verdict || "Passport Portrait Analyzed"}
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                {passport_face_detected
                  ? "Neural face detector confirmed human facial presence in bio-page."
                  : "Localized using ICAO TD3 biometric portrait quadrant."}
              </p>
              <div className="mt-2 flex items-center space-x-2">
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                  Splice Risk: <strong className={photoDet.photo_risk_score > 30 ? "text-rose-400" : "text-emerald-400"}>{photoDet.photo_risk_score || 0}/100</strong>
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                  Tilt: {icao.head_tilt_degrees !== undefined ? `${icao.head_tilt_degrees}°` : '0°'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Forensic Checks Indicators */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-xs">
          <div className="p-2 rounded bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] text-slate-400 block">Face Presence</span>
            <span className="font-bold text-emerald-400 text-xs">
              {icao.face_detected !== false ? "✓ Detected" : "✕ Missing"}
            </span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] text-slate-400 block">Eye Alignment</span>
            <span className={`font-bold text-xs ${icao.eyes_horizontal !== false ? "text-emerald-400" : "text-amber-400"}`}>
              {icao.eyes_horizontal !== false ? "✓ Level" : "⚠️ Tilted"}
            </span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] text-slate-400 block">Splice Perimeter</span>
            <span className={`font-bold text-xs ${photoDet.photo_risk_score >= 35 ? "text-rose-400" : "text-emerald-400"}`}>
              {photoDet.photo_risk_score >= 35 ? "✕ Discontinuity" : "✓ Seamless"}
            </span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800 text-center">
            <span className="text-[10px] text-slate-400 block">Photo ELA Noise</span>
            <span className={`font-bold text-xs ${(icao.photo_ela_std || 0) > 8 ? "text-amber-400" : "text-emerald-400"}`}>
              {icao.photo_ela_std ? `${icao.photo_ela_std} Std` : "Normal"}
            </span>
          </div>
        </div>

        {/* Flags list if photo triggered warnings */}
        {photoDet.flags && photoDet.flags.length > 0 && (
          <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300">
            <span className="font-semibold block mb-1">⚠️ Photo Determination Warnings:</span>
            <ul className="list-disc list-inside space-y-0.5 text-[11px] text-rose-200/90">
              {photoDet.flags.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 2. Biometric Facial Verification (Passport Crop vs Live Capture) */}
      <div className="pt-2">
        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center">
          <UserCheck className="w-3.5 h-3.5 mr-1.5 text-indigo-400" />
          1:1 Biometric Traveler Cross-Verification
        </h4>

        {performed ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col items-center bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
                <span className="text-[10px] font-semibold text-slate-400 mb-1.5">Passport Portrait</span>
                <div className="w-20 h-28 rounded bg-slate-900 overflow-hidden border border-slate-700">
                  <img src={passport_face_preview_base64} alt="Passport" className="w-full h-full object-cover" />
                </div>
              </div>

              <div className="flex flex-col items-center bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
                <span className="text-[10px] font-semibold text-slate-400 mb-1.5">Live Traveler Capture</span>
                <div className="w-20 h-28 rounded bg-slate-900 overflow-hidden border border-slate-700">
                  {live_face_preview_base64 ? (
                    <img src={live_face_preview_base64} alt="Live" className="w-full h-full object-cover" />
                  ) : (
                    <UserX className="w-6 h-6 text-slate-600 m-auto" />
                  )}
                </div>
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800 text-xs">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-slate-300 font-semibold">Biometric Facial Similarity:</span>
                <span className={`font-mono text-sm font-bold ${is_match ? 'text-indigo-400' : 'text-rose-400'}`}>
                  {match_score !== null ? `${match_score}%` : 'N/A'}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${
                    is_match ? 'bg-indigo-500' : 'bg-rose-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, match_score || 0))}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1">
                <span>Threshold: 60%</span>
                <span className="font-mono text-slate-400">{engine}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3.5 bg-slate-950/50 rounded-xl border border-slate-800/80 text-xs text-slate-400 flex items-center justify-between">
            <div>
              <p className="font-medium text-slate-300">Live traveler selfie was not provided.</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Upload or snap a webcam photo to compare 128-d deep facial embeddings.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Scope Disclaimer */}
      <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-900/40 flex items-start space-x-2 text-[11px] text-amber-300/90">
        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
        <span>
          <strong>Scope Limitation:</strong> {liveness_limitation_note || "Physical liveness / anti-spoofing is out of scope for this prototype."}
        </span>
      </div>
    </div>
  );
}
