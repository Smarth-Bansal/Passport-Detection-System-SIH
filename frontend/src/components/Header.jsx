import React from 'react';
import { ShieldCheck, AlertCircle, Database, Cpu, History, Info } from 'lucide-react';

export default function Header({ onOpenHistory, onOpenLimitations, historyCount }) {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 px-4 lg:px-8 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* Left Branding */}
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center">
                DocuVerify <span className="text-sky-400 text-xs font-semibold ml-2 px-2 py-0.5 rounded-full bg-sky-950 border border-sky-800">PASSPORT v1.0</span>
              </h1>
            </div>
            <p className="text-xs text-slate-400">
              AI-Assisted Border Credential Screening & Tampering Forensics
            </p>
          </div>
        </div>

        {/* Center Human-in-the-loop Badge */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
          <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <span>Decision Support System — Never Auto-Rejects</span>
        </div>

        {/* Right Tools */}
        <div className="flex items-center space-x-2.5">
          <button
            onClick={onOpenHistory}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
          >
            <History className="w-3.5 h-3.5 text-slate-400" />
            <span>Audit Trail</span>
            {historyCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 text-[10px] rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/40">
                {historyCount}
              </span>
            )}
          </button>

          <button
            onClick={onOpenLimitations}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
          >
            <Info className="w-3.5 h-3.5 text-sky-400" />
            <span>Limitations</span>
          </button>

          <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 text-[11px] text-slate-400 bg-slate-950 rounded-md border border-slate-800">
            <Cpu className="w-3.5 h-3.5 text-emerald-400" />
            <span>ONNX CPU Serving</span>
          </div>
        </div>
      </div>
    </header>
  );
}
