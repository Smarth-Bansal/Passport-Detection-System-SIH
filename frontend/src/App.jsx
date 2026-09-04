import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import UploadSection from './components/UploadSection';
import ScanPreview from './components/ScanPreview';
import ResultsDashboard from './components/ResultsDashboard';
import AuditHistoryTable from './components/AuditHistoryTable';
import LimitationsNotice from './components/LimitationsNotice';
import { AlertTriangle, X } from 'lucide-react';

export default function App() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [forceCrop, setForceCrop] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [limitationsOpen, setLimitationsOpen] = useState(false);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      const res = await fetch('/history');
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.warn("Could not fetch audit history:", err);
    }
  };

  const handleScreen = async ({ document_image, live_selfie, force_crop, crop_mode }) => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('document_image', document_image);
      if (live_selfie) {
        formData.append('live_selfie', live_selfie);
      }
      formData.append('force_crop', force_crop ? 'true' : 'false');
      formData.append('crop_mode', crop_mode || 'auto');

      const response = await fetch('/screen', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        if (response.status === 422 && errData.error === "SCANNER_ERROR") {
          throw new Error(errData.message || "Document border detection failed. Check passport placement.");
        }
        throw new Error(errData.detail || `Screening failed (Status ${response.status})`);
      }

      const data = await response.json();
      setResults(data);
      fetchLogs();
    } catch (err) {
      setError(err.message || "Network error while contacting screening service.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100">
      <Header
        onOpenHistory={() => setHistoryOpen(true)}
        onOpenLimitations={() => setLimitationsOpen(true)}
        historyCount={logs.length}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-8 space-y-8">
        {/* Error Alert Banner */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-950/80 border border-rose-600 text-rose-200 flex items-start justify-between shadow-lg">
            <div className="flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <strong className="font-bold text-sm block">Screening Exception Encountered:</strong>
                <span className="text-xs text-rose-200">{error}</span>
                <p className="text-[11px] text-rose-300/80 mt-1">
                  Tip: Enable "Force Full Crop" in Document Intake if the passport borders are outside the frame.
                </p>
              </div>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-rose-400 hover:text-white p-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* 1. Document Intake Section */}
        <UploadSection
          onScreen={handleScreen}
          loading={loading}
          forceCrop={forceCrop}
          setForceCrop={setForceCrop}
        />

        {/* 2. Auto-Scan & Perspective Correction Preview */}
        {results?.scan_metadata && (
          <ScanPreview
            scanMetadata={results.scan_metadata}
            elaHeatmapBase64={results?.tamper_signals?.error_level_analysis?.heatmap_base64}
          />
        )}

        {/* 3. Comprehensive Results Dashboard */}
        {results && (
          <ResultsDashboard results={results} />
        )}
      </main>

      {/* Audit Trail Modal */}
      <AuditHistoryTable
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        logs={logs}
        onSelectAudit={() => {}}
      />

      {/* Scope Limitations Modal */}
      <LimitationsNotice
        isOpen={limitationsOpen}
        onClose={() => setLimitationsOpen(false)}
      />

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 px-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>DocuVerify Decision Support System • Built with Python FastAPI, React, OpenCV & ONNX Runtime</span>
          <span>Human-in-the-loop: Assisted border control screening only • Not certified for live operations</span>
        </div>
      </footer>
    </div>
  );
}
