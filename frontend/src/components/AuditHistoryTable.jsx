import React, { useState } from 'react';
import { X, History, FileText, CheckCircle2, ShieldAlert, AlertTriangle, Download } from 'lucide-react';

export default function AuditHistoryTable({ isOpen, onClose, logs, onSelectAudit }) {
  const [selectedLog, setSelectedLog] = useState(null);

  if (!isOpen) return null;

  const getBadge = (rec) => {
    if (!rec) return null;
    if (rec.startsWith("HIGH")) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-800">HIGH RISK</span>;
    }
    if (rec.startsWith("MEDIUM")) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800">MANUAL REVIEW</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">LOW RISK</span>;
  };

  const exportLogsAsJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(logs, null, 2));
    const dl = document.createElement("a");
    dl.setAttribute("href", dataStr);
    dl.setAttribute("download", `docuverify_audit_trail_${new Date().toISOString().slice(0, 10)}.json`);
    dl.click();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-5xl w-full max-h-[85vh] flex flex-col shadow-2xl relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-sky-500/20 text-sky-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Digital Audit Trail & Verification Logs</h2>
              <p className="text-xs text-slate-400">Tamper-evident record of all processed credentials</p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={exportLogsAsJson}
              disabled={logs.length === 0}
              className="flex items-center space-x-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              <span>Export JSON</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {logs.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs">
              No documents screened in this session yet. Run a screening to view audit records.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/80 uppercase text-[10px] text-slate-400 tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Timestamp</th>
                    <th className="py-2.5 px-3">Audit UUID</th>
                    <th className="py-2.5 px-3">Passport #</th>
                    <th className="py-2.5 px-3">Traveler Name</th>
                    <th className="py-2.5 px-3">State</th>
                    <th className="py-2.5 px-3">Tamper Score</th>
                    <th className="py-2.5 px-3">Face Match</th>
                    <th className="py-2.5 px-3">Recommendation</th>
                    <th className="py-2.5 px-3 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-sky-400">
                        {log.id.slice(0, 8)}...
                      </td>
                      <td className="py-2.5 px-3 font-mono font-bold text-white">
                        {log.passport_number || 'UNKNOWN'}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-slate-200">
                        {log.traveler_name || 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-400">
                        {log.issuing_country || 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 font-mono font-bold">
                        <span className={log.tamper_risk_score >= 65 ? "text-rose-400" : log.tamper_risk_score >= 30 ? "text-amber-400" : "text-emerald-400"}>
                          {log.tamper_risk_score}/100
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-300">
                        {log.face_match_score !== null ? `${log.face_match_score}%` : '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        {getBadge(log.overall_recommendation)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => setSelectedLog(log)}
                          className="px-2 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-sky-400 rounded transition-colors"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Detailed Modal view if selected */}
          {selectedLog && (
            <div className="fixed inset-0 z-60 bg-slate-950/90 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full p-5 max-h-[80vh] flex flex-col">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <span className="font-bold text-sm text-white font-mono">
                    Audit Record: {selectedLog.id}
                  </span>
                  <button onClick={() => setSelectedLog(null)} className="text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto mt-3 p-3 bg-slate-950 rounded-lg text-xs font-mono text-emerald-400">
                  <pre>{JSON.stringify(selectedLog, null, 2)}</pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
