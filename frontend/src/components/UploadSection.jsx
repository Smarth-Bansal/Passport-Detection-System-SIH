import React, { useState, useRef } from 'react';
import { Upload, Camera, FileCheck, RefreshCw, AlertCircle, Sparkles, UserCheck } from 'lucide-react';

export default function UploadSection({
  onScreen,
  loading,
  onLoadSample,
  forceCrop,
  setForceCrop,
}) {
  const [docFile, setDocFile] = useState(null);
  const [docPreview, setDocPreview] = useState(null);
  const [selfieFile, setSelfieFile] = useState(null);
  const [selfiePreview, setSelfiePreview] = useState(null);
  const [isWebcamActive, setIsWebcamActive] = useState(false);

  const docInputRef = useRef(null);
  const selfieInputRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const handleDocDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectDocFile(e.dataTransfer.files[0]);
    }
  };

  const selectDocFile = (file) => {
    setDocFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setDocPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const selectSelfieFile = (file) => {
    setSelfieFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setSelfiePreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const startWebcam = async () => {
    try {
      setIsWebcamActive(true);
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      alert("Unable to access camera: " + err.message);
      setIsWebcamActive(false);
    }
  };

  const captureWebcamSelfie = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      const file = new File([blob], "live_selfie.jpg", { type: "image/jpeg" });
      selectSelfieFile(file);
      stopWebcam();
    }, "image/jpeg", 0.92);
  };

  const stopWebcam = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsWebcamActive(false);
  };

  const handleStartScreening = (e) => {
    e.preventDefault();
    if (!docFile) {
      alert("Please provide a passport bio-data image to screen.");
      return;
    }
    onScreen({
      document_image: docFile,
      live_selfie: selfieFile,
      force_crop: forceCrop,
    });
  };

  const handleSampleClick = (sampleType) => {
    onLoadSample(sampleType, (file, preview, selfieF, selfieP) => {
      setDocFile(file);
      setDocPreview(preview);
      if (selfieF) {
        setSelfieFile(selfieF);
        setSelfiePreview(selfieP);
      }
    });
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
      {/* Background radial highlight */}
      <div className="absolute -top-12 -left-12 w-48 h-48 bg-sky-500/5 rounded-full blur-2xl pointer-events-none" />

      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-base font-bold text-white flex items-center">
            <FileCheck className="w-5 h-5 mr-2 text-sky-400" />
            Document Intake & Traveler Capture
          </h2>
          <p className="text-xs text-slate-400">
            Accepts raw mobile photos, flatbed scans, or webcam frames (Auto-deskews ~1.42:1 TD3 bio-data page)
          </p>
        </div>

        {/* Demo Sample Quick-Loaders */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-slate-400 mr-1 flex items-center">
            <Sparkles className="w-3 h-3 text-amber-400 mr-1" /> Test Samples:
          </span>
          <button
            type="button"
            onClick={() => handleSampleClick("authentic")}
            className="px-2.5 py-1 text-[11px] font-medium bg-emerald-950/60 hover:bg-emerald-900/80 text-emerald-300 border border-emerald-800/80 rounded-md transition-colors"
          >
            Authentic Pass
          </button>
          <button
            type="button"
            onClick={() => handleSampleClick("tampered_photo")}
            className="px-2.5 py-1 text-[11px] font-medium bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800/80 rounded-md transition-colors"
          >
            Photo Splice (Tamper)
          </button>
          <button
            type="button"
            onClick={() => handleSampleClick("blacklisted")}
            className="px-2.5 py-1 text-[11px] font-medium bg-amber-950/60 hover:bg-amber-900/80 text-amber-300 border border-amber-800/80 rounded-md transition-colors"
          >
            Stolen / Blacklisted
          </button>
          <button
            type="button"
            onClick={() => handleSampleClick("bad_checksum")}
            className="px-2.5 py-1 text-[11px] font-medium bg-purple-950/60 hover:bg-purple-900/80 text-purple-300 border border-purple-800/80 rounded-md transition-colors"
          >
            Bad MRZ Checksum
          </button>
        </div>
      </div>

      <form onSubmit={handleStartScreening}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Document Upload Box */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wider">
              1. Passport Bio-Data Image <span className="text-rose-400">*</span>
            </label>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDocDrop}
              onClick={() => docInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl h-48 flex flex-col items-center justify-center p-4 cursor-pointer transition-all ${
                docPreview
                  ? "border-sky-500/60 bg-sky-950/20"
                  : "border-slate-700 hover:border-slate-500 bg-slate-800/40 hover:bg-slate-800/70"
              }`}
            >
              <input
                type="file"
                ref={docInputRef}
                onChange={(e) => e.target.files?.[0] && selectDocFile(e.target.files[0])}
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
              />

              {docPreview ? (
                <div className="relative w-full h-full flex items-center justify-center overflow-hidden rounded-lg">
                  <img
                    src={docPreview}
                    alt="Passport Preview"
                    className="max-h-full max-w-full object-contain rounded-md shadow-md"
                  />
                  <div className="absolute inset-0 bg-slate-950/40 opacity-0 hover:opacity-100 flex items-center justify-center text-white text-xs font-medium transition-opacity">
                    Click or drop to replace document
                  </div>
                </div>
              ) : (
                <div className="text-center space-y-2">
                  <div className="w-10 h-10 rounded-full bg-slate-800 text-sky-400 mx-auto flex items-center justify-center shadow">
                    <Upload className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-semibold text-slate-200">
                    Drag & drop passport image, or <span className="text-sky-400 underline">browse</span>
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Supports JPEG, PNG, WebP (Contour detector auto-crops TD3 page)
                  </p>
                </div>
              )}
            </div>

            <div className="mt-2.5 flex items-center justify-between text-xs">
              <label className="flex items-center space-x-2 text-slate-400 hover:text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceCrop}
                  onChange={(e) => setForceCrop(e.target.checked)}
                  className="rounded bg-slate-800 border-slate-700 text-sky-500 focus:ring-0 focus:ring-offset-0"
                />
                <span className="text-[11px]">Force full crop (bypass strict contour if scan is unbordered)</span>
              </label>
              {docFile && (
                <span className="text-[11px] text-slate-400 truncate max-w-[150px]">
                  {docFile.name}
                </span>
              )}
            </div>
          </div>

          {/* Live Traveler Selfie Box */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                2. Live Traveler Capture <span className="text-slate-500 font-normal">(Optional)</span>
              </label>
              {!isWebcamActive ? (
                <button
                  type="button"
                  onClick={startWebcam}
                  className="flex items-center space-x-1 text-[11px] text-sky-400 hover:text-sky-300 font-medium"
                >
                  <Camera className="w-3.5 h-3.5" />
                  <span>Open Camera</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={stopWebcam}
                  className="text-[11px] text-rose-400 hover:text-rose-300 font-medium"
                >
                  Cancel Camera
                </button>
              )}
            </div>

            <div
              className={`border-2 border-dashed rounded-xl h-48 flex flex-col items-center justify-center p-4 relative overflow-hidden ${
                selfiePreview
                  ? "border-indigo-500/60 bg-indigo-950/20"
                  : "border-slate-700 bg-slate-800/40"
              }`}
            >
              {isWebcamActive ? (
                <div className="relative w-full h-full flex flex-col items-center justify-center">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    className="w-full h-full object-cover rounded-lg"
                  />
                  <button
                    type="button"
                    onClick={captureWebcamSelfie}
                    className="absolute bottom-2 px-4 py-1.5 bg-sky-500 hover:bg-sky-400 text-white font-semibold text-xs rounded-full shadow-lg flex items-center space-x-1.5"
                  >
                    <Camera className="w-3.5 h-3.5" />
                    <span>Snap Traveler Face</span>
                  </button>
                </div>
              ) : selfiePreview ? (
                <div
                  onClick={() => selfieInputRef.current?.click()}
                  className="relative w-full h-full flex items-center justify-center cursor-pointer"
                >
                  <img
                    src={selfiePreview}
                    alt="Traveler Selfie"
                    className="max-h-full max-w-full object-contain rounded-md shadow-md"
                  />
                  <div className="absolute inset-0 bg-slate-950/40 opacity-0 hover:opacity-100 flex items-center justify-center text-white text-xs font-medium transition-opacity">
                    Click to replace selfie
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => selfieInputRef.current?.click()}
                  className="text-center space-y-2 cursor-pointer"
                >
                  <div className="w-10 h-10 rounded-full bg-slate-800 text-indigo-400 mx-auto flex items-center justify-center shadow">
                    <UserCheck className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-semibold text-slate-200">
                    Capture webcam selfie or <span className="text-indigo-400 underline">browse photo</span>
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Compares live face against extracted passport portrait crop
                  </p>
                </div>
              )}

              <input
                type="file"
                ref={selfieInputRef}
                onChange={(e) => e.target.files?.[0] && selectSelfieFile(e.target.files[0])}
                accept="image/jpeg,image/png"
                className="hidden"
              />
            </div>

            <div className="mt-2.5 flex items-center justify-between text-xs">
              <span className="text-[11px] text-slate-400 italic">
                Note: Liveness verification is out of scope
              </span>
              {selfieFile && (
                <button
                  type="button"
                  onClick={() => {
                    setSelfieFile(null);
                    setSelfiePreview(null);
                  }}
                  className="text-[11px] text-rose-400 hover:underline"
                >
                  Clear selfie
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Submit Screening Button */}
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800">
          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <AlertCircle className="w-4 h-4 text-sky-400 flex-shrink-0" />
            <span>5 forensic pipelines will execute sequentially (Scanner → OCR → Validator → Tamper Ensemble → Face)</span>
          </div>

          <button
            type="submit"
            disabled={loading || !docFile}
            className={`w-full sm:w-auto px-6 py-2.5 rounded-xl font-semibold text-xs tracking-wide uppercase transition-all shadow-lg flex items-center justify-center space-x-2 ${
              loading || !docFile
                ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                : "bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white shadow-sky-600/30"
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-white" />
                <span>Running Screening Pipeline...</span>
              </>
            ) : (
              <>
                <FileCheck className="w-4 h-4" />
                <span>Screen Document for Risk</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
