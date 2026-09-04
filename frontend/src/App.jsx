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

  /**
   * Generates synthetic passport test canvas samples on the fly
   * to allow testing without requiring manual file prep.
   */
  const handleLoadSample = (sampleType, onReady) => {
    const canvas = document.createElement("canvas");
    canvas.width = 1420;
    canvas.height = 1000;
    const ctx = canvas.getContext("2d");

    // Background passport bio-data page
    ctx.fillStyle = "#f8fafc";
    ctx.fillRect(0, 0, 1420, 1000);

    // Decorative passport microprint background lines
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    for (let y = 100; y < 750; y += 12) {
      ctx.beginPath();
      ctx.moveTo(40, y);
      ctx.lineTo(1380, y);
      ctx.stroke();
    }

    // Outer passport border
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 3;
    ctx.strokeRect(30, 30, 1360, 940);

    // Header
    ctx.fillStyle = "#0f172a";
    ctx.font = "bold 34px sans-serif";
    ctx.fillText("PASSPORT / PASSEPORT", 480, 90);
    ctx.font = "26px sans-serif";
    ctx.fillStyle = "#334155";
    ctx.fillText("UNITED STATES OF AMERICA", 480, 135);

    // Photo frame zone (ICAO left zone)
    ctx.fillStyle = "#cbd5e1";
    ctx.fillRect(60, 180, 380, 520);
    ctx.strokeStyle = "#64748b";
    ctx.lineWidth = 2;
    ctx.strokeRect(60, 180, 380, 520);

    // Synthetic Portrait Drawing
    ctx.fillStyle = "#fed7aa"; // skin tone
    ctx.beginPath();
    ctx.arc(250, 390, 105, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#1e293b"; // hair
    ctx.beginPath();
    ctx.arc(250, 330, 110, Math.PI, 0);
    ctx.fill();

    ctx.fillStyle = "#0f172a"; // eyes
    ctx.fillRect(205, 375, 18, 10);
    ctx.fillRect(275, 375, 18, 10);

    ctx.strokeStyle = "#e11d48"; // mouth
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(250, 430, 35, 0.2, Math.PI - 0.2);
    ctx.stroke();

    // If tampered photo sample, splice an altered patch with mismatched color
    if (sampleType === "tampered_photo") {
      ctx.fillStyle = "rgba(180, 50, 50, 0.25)";
      ctx.fillRect(100, 240, 290, 380);
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 1;
      ctx.strokeRect(100, 240, 290, 380);
      ctx.fillStyle = "#450a0a";
      ctx.font = "14px monospace";
      ctx.fillText("[PHOTO SPLICED DISCORDANCE]", 110, 230);
    }

    // Visual Text Fields
    ctx.fillStyle = "#0f172a";
    ctx.font = "bold 20px sans-serif";
    ctx.fillText("Type / Type: P", 500, 220);
    ctx.fillText("Code: USA", 760, 220);

    let passNum = "123456789";
    let surname = "DOE";
    let given = "JOHN";
    let dob = "900101"; // 1990-01-01
    let exp = "300101"; // 2030-01-01
    let pChk = "7";
    let dobChk = "4";
    let expChk = "6";

    if (sampleType === "blacklisted") {
      passNum = "L898902C3";
      pChk = "3";
    } else if (sampleType === "bad_checksum") {
      // Alter check digit on purpose to trigger checksum failure
      expChk = "9"; // wrong check digit!
    }

    ctx.fillText(`Passport No: ${passNum}`, 960, 220);
    ctx.fillText(`Surname / Nom: ${surname}`, 500, 300);
    ctx.fillText(`Given Names / Prénoms: ${given}`, 500, 370);
    ctx.fillText("Nationality / Nationalité: UNITED STATES OF AMERICA", 500, 440);
    ctx.fillText("Date of Birth: 01 JAN 1990", 500, 510);
    ctx.fillText("Sex / Sexe: M", 960, 510);
    ctx.fillText("Authority: UNITED STATES DEPARTMENT OF STATE", 500, 580);

    // Bottom TD3 MRZ Zone (2 lines of 44 characters)
    ctx.fillStyle = "#020617";
    ctx.fillRect(40, 780, 1340, 175);

    ctx.fillStyle = "#22c55e"; // MRZ characters in green terminal style for clarity
    ctx.font = "bold 28px monospace";

    const line1 = `P<USA${surname}<<${given}`.padEnd(44, '<');
    const compData = `${passNum}${pChk}${dob}${dobChk}${exp}${expChk}<<<<<<<<<<<<<<`;
    const compChk = "4";
    const line2 = `${passNum}${pChk}USA${dob}${dobChk}M${exp}${expChk}<<<<<<<<<<<<<<${compChk}`;

    ctx.fillText(line1, 70, 840);
    ctx.fillText(line2, 70, 910);

    canvas.toBlob((blob) => {
      const file = new File([blob], `${sampleType}_passport.jpg`, { type: "image/jpeg" });
      const previewUrl = URL.createObjectURL(blob);

      // Create synthetic selfie face
      const selfieCanvas = document.createElement("canvas");
      selfieCanvas.width = 400;
      selfieCanvas.height = 400;
      const sCtx = selfieCanvas.getContext("2d");
      sCtx.fillStyle = "#0f172a";
      sCtx.fillRect(0, 0, 400, 400);
      sCtx.fillStyle = "#fed7aa";
      sCtx.beginPath();
      sCtx.arc(200, 200, 110, 0, Math.PI * 2);
      sCtx.fill();
      sCtx.fillStyle = "#0f172a";
      sCtx.fillRect(155, 185, 20, 12);
      sCtx.fillRect(225, 185, 20, 12);
      sCtx.strokeStyle = "#e11d48";
      sCtx.lineWidth = 3;
      sCtx.beginPath();
      sCtx.arc(200, 245, 35, 0.2, Math.PI - 0.2);
      sCtx.stroke();

      selfieCanvas.toBlob((sBlob) => {
        const selfieFile = new File([sBlob], "traveler_live.jpg", { type: "image/jpeg" });
        const selfiePreviewUrl = URL.createObjectURL(sBlob);
        onReady(file, previewUrl, selfieFile, selfiePreviewUrl);
      }, "image/jpeg", 0.9);
    }, "image/jpeg", 0.92);
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
          onLoadSample={handleLoadSample}
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
