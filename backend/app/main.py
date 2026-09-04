import os
import uuid
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import (
    APP_NAME,
    APP_VERSION,
    APP_DESCRIPTION,
    MODEL_VERSION,
    KAGGLE_NOTEBOOK_REF,
    TAMPER_RISK_LOW_MAX,
    TAMPER_RISK_MEDIUM_MAX,
)
from .database import (
    init_db,
    get_db,
    save_audit_record,
    get_audit_logs,
    get_audit_by_id,
    sanitize_for_json,
)
from .services import (
    scan_passport,
    ScannerError,
    extract_document_fields,
    validate_document,
    detect_tampering,
    compare_faces,
)

# Initialize database tables on startup
init_db()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)

# CORS setup for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
        "model_version": MODEL_VERSION,
        "kaggle_notebook": KAGGLE_NOTEBOOK_REF,
        "notice": "Decision support prototype for authorized human reviewers only. Never auto-rejects."
    }


def compute_recommendation(
    tamper_risk_score: float,
    validation_result: dict,
    mrz_checksum_valid: bool,
    face_match_result: dict,
) -> str:
    """
    Computes an officer advisory recommendation.
    Policy: Never auto-reject. System only flags risk level for human adjudication.
    """
    issues = validation_result.get("issues", [])
    has_critical_validation_error = any(i.get("type") == "error" for i in issues)
    mock_db_matched = validation_result.get("mock_db_result", {}).get("matched", False)

    # Secondary inspection flags
    if (
        tamper_risk_score >= TAMPER_RISK_MEDIUM_MAX
        or not mrz_checksum_valid
        or mock_db_matched
        or (face_match_result.get("performed") and face_match_result.get("match_score", 100) < 40.0)
    ):
        return "HIGH — flag for secondary inspection"

    # Manual review flags
    if (
        tamper_risk_score >= TAMPER_RISK_LOW_MAX
        or has_critical_validation_error
        or len(issues) > 0
        or (face_match_result.get("performed") and not face_match_result.get("is_match", True))
    ):
        return "MEDIUM — manual review"

    return "LOW RISK — proceed"


@app.post("/screen")
async def screen_document(
    document_image: UploadFile = File(..., description="Image of passport bio-data page"),
    live_selfie: Optional[UploadFile] = File(None, description="Optional live traveler webcam snapshot"),
    force_crop: bool = Form(False, description="If true, bypass strict 1.42:1 contour detection on failure"),
    crop_mode: str = Form("auto", description="Crop strategy: 'auto', 'bottom_half', 'top_half', 'full'"),
    db: Session = Depends(get_db),
):
    """
    Orchestrates the 5-module document screening pipeline:
    1. Auto-Scan & Preprocessing (Contour detection, deskew, glare correction)
    2. MRZ & OCR Extraction (PassportEye TD3 + Tesseract VIZ)
    3. Document Validation (ICAO 7-3-1 Checksum, date logic, country regex, mock blacklist)
    4. Tampering Detection (ONNX CNN inference + ELA diff heatmap + EXIF forensics)
    5. Face Verification (Passport photo crop vs live capture)
    """
    # Read uploaded bytes
    try:
        doc_bytes = await document_image.read()
        if not doc_bytes:
            raise HTTPException(status_code=400, detail="Empty document image uploaded.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read document image: {str(e)}")

    selfie_bytes = None
    if live_selfie is not None:
        try:
            selfie_bytes = await live_selfie.read()
            if len(selfie_bytes) == 0:
                selfie_bytes = None
        except Exception:
            selfie_bytes = None

    # Step 1: Auto-Scan & Perspective Preprocessing
    try:
        scan_result = scan_passport(doc_bytes, force_fallback=force_crop, crop_mode=crop_mode)
    except ScannerError as se:
        return JSONResponse(
            status_code=422,
            content={
                "error": "SCANNER_ERROR",
                "message": str(se),
                "suggestion": "Place passport flat against a contrasting background with all 4 corners visible, or select 'Bottom Half (Open Passport)' / 'Force Full Crop' in crop settings."
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preprocessing error: {str(e)}")

    cropped_bgr = scan_result["cropped_bgr"]

    # Step 2: MRZ + OCR Extraction
    ocr_result = extract_document_fields(cropped_bgr)
    mrz_data = ocr_result.get("mrz", {})
    mrz_found = mrz_data.get("found", False)
    mrz_checksum_valid = ocr_result.get("all_checksums_pass", False)

    # Extract high-level traveler info
    fields = mrz_data.get("fields", {})
    passport_number = fields.get("passport_number", {}).get("value")
    traveler_name = fields.get("full_name", {}).get("value")
    nationality = fields.get("nationality", {}).get("value")
    issuing_country = fields.get("issuing_country", {}).get("value")

    # Step 3: Document Validation & Mock Database Lookup
    validation_result = validate_document(ocr_result)

    # Step 4: Tampering Detection (ONNX CNN + ELA + EXIF Forensics + MRZ Signal)
    tamper_result = detect_tampering(
        image_bgr=cropped_bgr,
        raw_image_bytes=doc_bytes,
        mrz_checksum_valid=mrz_checksum_valid if mrz_found else False
    )

    # Step 5: Face Verification & Photo Determination
    face_result = compare_faces(
        passport_image_bgr=cropped_bgr,
        live_selfie_bytes=selfie_bytes
    )

    photo_det = face_result.get("photo_determination", {})
    if photo_det.get("is_flagged"):
        for flg in photo_det.get("flags", []):
            if flg not in tamper_result["triggered_signals"]:
                tamper_result["triggered_signals"].append(f"Photo: {flg}")

    # Incorporate photo tampering risk into composite tamper score
    if photo_det.get("photo_risk_score", 0) > 40.0:
        # Boost tamper risk score with photo splice evidence
        boosted_score = max(tamper_result["tamper_risk_score"], photo_det.get("photo_risk_score", 0))
        tamper_result["tamper_risk_score"] = round(boosted_score, 1)

    # Step 6: Recommendation Calculation
    overall_recommendation = compute_recommendation(
        tamper_risk_score=tamper_result["tamper_risk_score"],
        validation_result=validation_result,
        mrz_checksum_valid=mrz_checksum_valid,
        face_match_result=face_result,
    )

    # Assemble complete payload
    raw_payload = {
        "scan_metadata": {
            "contour_detected": scan_result["contour_detected"],
            "aspect_ratio": scan_result["aspect_ratio"],
            "crop_method": scan_result.get("crop_method", "Auto"),
            "dimensions": scan_result["dimensions"],
            "preview_cropped_base64": scan_result["preview_cropped_base64"],
            "preview_original_base64": scan_result["preview_original_base64"],
        },
        "extracted_fields": fields,
        "mrz_raw_lines": mrz_data.get("raw_lines", []),
        "mrz_checksum_valid": mrz_checksum_valid,
        "mrz_found": mrz_found,
        "viz_cross_checks": ocr_result.get("cross_checks", []),
        "validation": {
            "passed": validation_result["passed"],
            "issues": validation_result["issues"],
            "checks_run": validation_result["checks_run"],
            "mock_db_result": validation_result["mock_db_result"],
        },
        "tamper_risk_score": tamper_result["tamper_risk_score"],
        "tamper_signals": tamper_result["signal_breakdown"],
        "triggered_tamper_signals": tamper_result["triggered_signals"],
        "face_match": face_result,
        "overall_recommendation": overall_recommendation,
        "human_officer_guidance": (
            "This automated output is a decision-support indicator for trained immigration officers. "
            "Never auto-reject a passenger solely on this automated score."
        ),
        "model_version": MODEL_VERSION,
        "kaggle_notebook_ref": KAGGLE_NOTEBOOK_REF,
    }

    # Ensure all nested values are 100% native JSON-serializable primitives (cleans numpy bools/floats)
    screening_payload = sanitize_for_json(raw_payload)

    # Step 7: Audit Log Persistence
    audit_entry = save_audit_record(
        db=db,
        passport_number=passport_number,
        traveler_name=traveler_name,
        nationality=nationality,
        issuing_country=issuing_country,
        mrz_checksum_valid=mrz_checksum_valid,
        tamper_risk_score=tamper_result["tamper_risk_score"],
        face_match_score=face_result.get("match_score"),
        overall_recommendation=overall_recommendation,
        model_version=MODEL_VERSION,
        raw_result=screening_payload,
    )

    screening_payload["audit_id"] = str(audit_entry.id)
    screening_payload["audit_timestamp"] = audit_entry.timestamp.isoformat()

    return screening_payload


@app.get("/history")
def get_screening_history(limit: int = 50, db: Session = Depends(get_db)):
    """Returns past screening audit logs for border control digital trail."""
    logs = get_audit_logs(db, limit=limit)
    return [log.to_dict() for log in logs]


@app.get("/audit/{audit_id}")
def get_audit_detail(audit_id: str, db: Session = Depends(get_db)):
    """Retrieves full forensic details of a specific screening event by UUID."""
    entry = get_audit_by_id(db, audit_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit log record not found.")
    return entry.to_dict()


# Mount static frontend build if present
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_frontend_spa(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
