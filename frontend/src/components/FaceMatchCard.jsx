import React from 'react';
import { UserCheck, UserX, AlertTriangle, ShieldCheck } from 'lucide-react';

export default function FaceMatchCard({ faceMatch }) {
  if (!faceMatch) return null;

  const {
    performed,
    passport_face_detected,
    live_face_detected,
    match_score,
    is_match,
    engine,
    passport_face_preview_base64,
    live_face_preview_base64,
    liveness_limitation_note,
    message
  } = faceMatch;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Module 5: Facial Verification</h3>
            <p className="text-xs text-slate-400">Compares Passport Photo Crop vs Live Traveler Snapshot</p>
          </div>
        </div>

        {performed && match_score !== null && (
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
              is_match
                ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                : "bg-rose-950 text-rose-300 border-rose-800"
            }`}
          >
            {is_match ? "FACIAL MATCH CONFIRMED" : "LOW SIMILARITY"}
          </span>
        )}
      </div>

      {performed ? (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Passport Face Crop */}
            <div className="flex flex-col items-center bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Passport Photo Crop
              </span>
              <div className="w-28 h-36 rounded-lg bg-slate-900 overflow-hidden border border-slate-700 flex items-center justify-center">
                {passport_face_preview_base64 ? (
                  <img
                    src={passport_face_preview_base64}
                    alt="Passport Face"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-xs text-slate-500">No face crop</span>
                )}
              </div>
              <span className="text-[10px] text-slate-500 mt-1.5 font-mono">ICAO Portrait Zone</span>
            </div>

            {/* Live Traveler Selfie */}
            <div className="flex flex-col items-center bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Live Traveler Capture
              </span>
              <div className="w-28 h-36 rounded-lg bg-slate-900 overflow-hidden border border-slate-700 flex items-center justify-center">
                {live_face_preview_base64 ? (
                  <img
                    src={live_face_preview_base64}
                    alt="Live Face"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-xs text-slate-500">No live face</span>
                )}
              </div>
              <span className="text-[10px] text-slate-500 mt-1.5 font-mono">Webcam Capture</span>
            </div>
          </div>

          {/* Similarity Gauge Bar */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-slate-300 font-semibold">Visual Similarity Score:</span>
              <span className="font-mono text-sm font-bold text-indigo-400">
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
              <span>Engine: {engine || 'Face Recognition'}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 p-4 rounded-xl bg-slate-950/40 border border-slate-800 flex items-center space-x-3">
          <div className="w-16 h-20 rounded bg-slate-900 border border-slate-800 flex-shrink-0 overflow-hidden flex items-center justify-center">
            {passport_face_preview_base64 ? (
              <img src={passport_face_preview_base64} alt="Passport Crop" className="w-full h-full object-cover" />
            ) : (
              <UserX className="w-6 h-6 text-slate-600" />
            )}
          </div>
          <div className="text-xs text-slate-400">
            <p className="font-medium text-slate-300">Passport photo region extracted successfully.</p>
            <p className="text-[11px] mt-1 text-slate-500">
              Live webcam capture was not supplied for biometric 1:1 cross-matching.
            </p>
          </div>
        </div>
      )}

      {/* Mandatory Scope Limitation Note */}
      <div className="mt-3 p-2.5 rounded-lg bg-amber-950/30 border border-amber-900/40 flex items-start space-x-2 text-[11px] text-amber-300/90">
        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
        <span>
          <strong>Scope Limitation:</strong> {liveness_limitation_note || "Liveness / anti-spoofing detection is out of scope for this prototype."}
        </span>
      </div>
    </div>
  );
}
