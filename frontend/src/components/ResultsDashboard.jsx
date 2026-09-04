import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Database,
  FileText,
  User,
  Calendar,
  Globe,
  Hash,
  Binary,
  Layers
} from 'lucide-react';
import TamperBreakdown from './TamperBreakdown';
import FaceMatchCard from './FaceMatchCard';

export default function ResultsDashboard({ results }) {
  const [showRawMrz, setShowRawMrz] = useState(false);

  if (!results) return null;

  const {
    overall_recommendation,
    human_officer_guidance,
    audit_id,
    audit_timestamp,
    extracted_fields,
    mrz_raw_lines,
    mrz_checksum_valid,
    mrz_found,
    viz_cross_checks,
    validation,
    tamper_risk_score,
    tamper_signals,
    triggered_tamper_signals,
    face_match,
    model_version,
  } = results;

  const getRecommendationStyle = (rec) => {
    if (rec.startsWith("HIGH")) {
      return {
        bg: "bg-rose-950/80 border-rose-600 text-rose-200",
        badge: "bg-rose-600 text-white",
        icon: <ShieldAlert className="w-8 h-8 text-rose-400 flex-shrink-0" />,
        accent: "border-l-4 border-l-rose-500",
      };
    }
    if (rec.startsWith("MEDIUM")) {
      return {
        bg: "bg-amber-950/80 border-amber-600 text-amber-200",
        badge: "bg-amber-600 text-slate-950",
        icon: <AlertTriangle className="w-8 h-8 text-amber-400 flex-shrink-0" />,
        accent: "border-l-4 border-l-amber-500",
      };
    }
    return {
      bg: "bg-emerald-950/80 border-emerald-600 text-emerald-200",
      badge: "bg-emerald-600 text-white",
      icon: <ShieldCheck className="w-8 h-8 text-emerald-400 flex-shrink-0" />,
      accent: "border-l-4 border-l-emerald-500",
    };
  };

  const recStyle = getRecommendationStyle(overall_recommendation || "LOW RISK — proceed");
  const mockDb = validation?.mock_db_result || {};

  return (
    <div className="space-y-6">
      {/* 1. Big Color-Coded Recommendation Banner */}
      <div className={`p-6 rounded-2xl border ${recStyle.bg} ${recStyle.accent} shadow-2xl relative overflow-hidden`}>
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            {recStyle.icon}
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs uppercase tracking-widest font-mono text-slate-300">
                  Advisory Verdict
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  Audit Ref: {audit_id ? audit_id.slice(0, 8) : 'N/A'}
                </span>
              </div>
              <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white mt-0.5">
                {overall_recommendation}
              </h2>
              <p className="text-xs text-slate-300/90 mt-1 max-w-2xl font-medium">
                {human_officer_guidance}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-end text-right space-y-1">
            <span className="text-[11px] text-slate-400 font-mono">
              Screened: {audit_timestamp ? new Date(audit_timestamp).toLocaleTimeString() : 'Just now'}
            </span>
            <span className="px-2.5 py-1 rounded-md bg-slate-900/80 border border-slate-700 text-[11px] font-mono text-sky-400">
              Model: {model_version}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Mock Blacklist Alert (if triggered) */}
      {mockDb.matched && (
        <div className="p-4 rounded-xl bg-rose-950/90 border border-rose-600 text-rose-200 shadow-lg flex items-start space-x-3">
          <Database className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs">
            <div className="flex items-center space-x-2">
              <strong className="text-sm font-bold text-white uppercase tracking-wider">
                DOCUMENT ALERT: {mockDb.database_source}
              </strong>
              <span className="px-2 py-0.5 text-[10px] rounded bg-rose-900 border border-rose-700 font-bold">
                SIMULATION STAND-IN
              </span>
            </div>
            <p className="mt-1 text-rose-200">{mockDb.reason}</p>
            <p className="mt-1 text-[11px] text-rose-300/80 italic">{mockDb.note}</p>
          </div>
        </div>
      )}

      {/* 3. Main Dashboard Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Forensic Risk & Biometrics (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <TamperBreakdown
            tamperRiskScore={tamper_risk_score}
            signals={tamper_signals}
            triggeredSignals={triggered_tamper_signals}
          />
          <FaceMatchCard faceMatch={face_match} />
        </div>

        {/* Right Column: MRZ Extracted Data & Validation (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* MRZ Extracted Fields Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400">
                  <Binary className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Module 2: MRZ Extraction</h3>
                  <p className="text-xs text-slate-400">PassportEye ICAO TD3 Parser & Checksum Status</p>
                </div>
              </div>

              <span
                className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                  mrz_checksum_valid
                    ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                    : "bg-rose-950 text-rose-300 border-rose-800"
                }`}
              >
                {mrz_checksum_valid ? "CHECKSUMS PASS" : "CHECKSUM FAILED"}
              </span>
            </div>

            {mrz_found ? (
              <div className="space-y-3 text-xs">
                {/* Passport Number */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                  <span className="text-slate-400 flex items-center font-medium">
                    <Hash className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
                    Passport Number:
                  </span>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono font-bold text-white text-sm">
                      {extracted_fields?.passport_number?.value || "N/A"}
                    </span>
                    {extracted_fields?.passport_number?.checksum_valid ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" title="Check Digit Valid" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-400" title="Check Digit Invalid" />
                    )}
                  </div>
                </div>

                {/* Traveler Full Name */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                  <span className="text-slate-400 flex items-center font-medium">
                    <User className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
                    Traveler Name:
                  </span>
                  <span className="font-bold text-white">
                    {extracted_fields?.full_name?.value || "N/A"}
                  </span>
                </div>

                {/* Nationality & Issuing State */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[11px] text-slate-400 block mb-1">Nationality:</span>
                    <span className="font-mono font-bold text-white text-sm">
                      {extracted_fields?.nationality?.value || "N/A"}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[11px] text-slate-400 block mb-1">Issuing State:</span>
                    <span className="font-mono font-bold text-white text-sm">
                      {extracted_fields?.issuing_country?.value || "N/A"}
                    </span>
                  </div>
                </div>

                {/* DOB & Expiry */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[11px] text-slate-400 block mb-1">Date of Birth (YYMMDD):</span>
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-white">
                        {extracted_fields?.dob?.value || "N/A"}
                      </span>
                      {extracted_fields?.dob?.checksum_valid ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-400" />
                      )}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <span className="text-[11px] text-slate-400 block mb-1">Expiry Date (YYMMDD):</span>
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-white">
                        {extracted_fields?.expiry_date?.value || "N/A"}
                      </span>
                      {extracted_fields?.expiry_date?.checksum_valid ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-400" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Raw MRZ Toggle */}
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setShowRawMrz(!showRawMrz)}
                    className="text-[11px] text-sky-400 hover:text-sky-300 font-medium"
                  >
                    {showRawMrz ? "Hide 2-Line MRZ Strings" : "View Raw 2-Line MRZ Strings"}
                  </button>

                  {showRawMrz && mrz_raw_lines && (
                    <div className="mt-2 p-2.5 rounded-lg bg-slate-950 font-mono text-[11px] text-emerald-400 border border-slate-800 break-all space-y-1">
                      <div>{mrz_raw_lines[0]}</div>
                      <div>{mrz_raw_lines[1]}</div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900 text-amber-300 text-xs">
                No Machine Readable Zone (MRZ) detected on passport document.
              </div>
            )}
          </div>

          {/* Module 3: Validation & Chronology Checks */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Module 3: Integrity & Date Logic</h3>
                  <p className="text-xs text-slate-400">ICAO Doc 9303 Compliance & Format Rules</p>
                </div>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                  validation?.passed
                    ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                    : "bg-rose-950 text-rose-300 border-rose-800"
                }`}
              >
                {validation?.passed ? "ALL RULES PASSED" : "ISSUES FLAGGED"}
              </span>
            </div>

            {/* Validation Issues List */}
            {validation?.issues && validation.issues.length > 0 ? (
              <div className="space-y-2">
                {validation.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-lg border text-xs flex items-start space-x-2 ${
                      issue.type === "error"
                        ? "bg-rose-950/50 border-rose-800/80 text-rose-200"
                        : "bg-amber-950/50 border-amber-800/80 text-amber-200"
                    }`}
                  >
                    {issue.type === "error" ? (
                      <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    )}
                    <div>
                      <span className="font-semibold block font-mono text-[10px] uppercase">
                        [{issue.code}]
                      </span>
                      <span>{issue.message}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center space-x-2 text-xs text-emerald-400 p-2.5 bg-emerald-950/30 rounded-lg border border-emerald-900/50">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Date chronology, format regex, and character sets verified valid.</span>
              </div>
            )}

            {/* VIZ Cross Checks */}
            {viz_cross_checks && viz_cross_checks.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-800 text-xs">
                <span className="text-slate-400 font-semibold block mb-2">
                  Visual Inspection Zone (VIZ) Cross-Check:
                </span>
                <div className="space-y-1.5">
                  {viz_cross_checks.map((cc, i) => (
                    <div key={i} className="flex items-center justify-between text-[11px] p-1.5 rounded bg-slate-950 border border-slate-800">
                      <span className="capitalize text-slate-300">{cc.field}:</span>
                      <span className={cc.viz_match ? "text-emerald-400 font-medium" : "text-amber-400 font-medium"}>
                        {cc.viz_match ? "Confirmed in VIZ" : "Unverified in VIZ"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
