import React from 'react';
import { X, ShieldAlert, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function LimitationsNotice({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative overflow-hidden">
        {/* Glow */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">System Limitations & Scope Notice</h2>
              <p className="text-xs text-slate-400">Prototype Constraints & Regulatory Disclaimers</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="py-5 space-y-4 text-sm text-slate-300">
          <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-start space-x-3">
            <ShieldAlert className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-xs uppercase tracking-wider">
                1. Stand-in Mock Database Only
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                No live connection to INTERPOL Stolen and Lost Travel Documents (SLTD) or national police databases exists.
                All watchlist checks query a simulated local mock CSV table for demonstration and testing.
              </p>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-start space-x-3">
            <ShieldAlert className="w-5 h-5 text-sky-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-xs uppercase tracking-wider">
                2. No Liveness / Anti-Spoofing Detection
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                Facial matching verifies geometric and visual feature similarity between passport portrait crop and live webcam snapshot.
                Physical liveness verification, 3D depth analysis, and presentation attack detection (PAD) are out of scope.
              </p>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-start space-x-3">
            <ShieldAlert className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-xs uppercase tracking-wider">
                3. Decision Support — Never Automated Rejection
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                This system outputs risk probabilities and forensic cues to assist trained immigration officers.
                It is strictly forbidden from executing automated adverse administrative actions or traveler rejections.
              </p>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-start space-x-3">
            <ShieldAlert className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-white text-xs uppercase tracking-wider">
                4. Not Certified for Live Border Operations
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                This software is a research and prototyping platform. Deployment in operational border control environments
                requires formal accreditation under ICAO Doc 9303, ISO/IEC 19794, and regional national immigration authority standards.
              </p>
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg shadow-md transition-colors"
          >
            I Acknowledge Scope & Limitations
          </button>
        </div>
      </div>
    </div>
  );
}
