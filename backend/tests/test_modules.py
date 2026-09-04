import os
import cv2
import numpy as np
import pytest
from datetime import date, timedelta

from backend.app.services.scanner import (
    order_points,
    four_point_transform,
    correct_glare_and_shadow,
    sharpen_document,
    scan_passport,
    ScannerError,
)
from backend.app.services.ocr_engine import (
    compute_icao_check_digit,
    parse_mrz_lines,
    extract_mrz,
    extract_document_fields,
)
from backend.app.services.validator import (
    parse_mrz_date,
    query_mock_blacklist,
    validate_document,
)
from backend.app.services.tamper_detector import (
    compute_error_level_analysis,
    analyze_exif_forensics,
    detect_tampering,
)
from backend.app.services.face_match import (
    fallback_feature_similarity,
    compare_faces,
)


def create_synthetic_passport_image() -> np.ndarray:
    """Generates a synthetic 1420x1000 TD3 passport bio-data image for unit testing."""
    img = np.ones((1000, 1420, 3), dtype=np.uint8) * 245
    # Add border
    cv2.rectangle(img, (20, 20), (1400, 980), (200, 200, 200), 2)
    # Header
    cv2.putText(img, "PASSPORT / PASSEPORT", (500, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (30, 30, 30), 2)
    cv2.putText(img, "UNITED STATES OF AMERICA", (500, 125), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (50, 50, 50), 2)
    # Synthetic Portrait photo box on the left (ICAO zone)
    cv2.rectangle(img, (60, 180), (460, 700), (180, 190, 200), -1)
    # Draw simple face-like shape in photo box
    cv2.circle(img, (260, 380), 100, (230, 210, 190), -1)
    cv2.circle(img, (220, 360), 12, (50, 50, 50), -1)
    cv2.circle(img, (300, 360), 12, (50, 50, 50), -1)
    cv2.ellipse(img, (260, 420), (40, 20), 0, 0, 180, (50, 50, 50), 3)

    # Visual Inspection text
    cv2.putText(img, "Type / Type: P", (520, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    cv2.putText(img, "Code: USA", (750, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    cv2.putText(img, "Passport No: 123456789", (950, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    cv2.putText(img, "Surname: DOE", (520, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2)
    cv2.putText(img, "Given Names: JOHN", (520, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2)
    cv2.putText(img, "Nationality: UNITED STATES OF AMERICA", (520, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    cv2.putText(img, "Date of birth: 01 JAN 1990", (520, 510), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)

    # 2-Line TD3 MRZ Zone at bottom
    line1 = "P<USADOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    # Calculate valid check digits for line 2
    p_num = "123456789"
    p_chk = compute_icao_check_digit(p_num)
    dob = "900101"
    dob_chk = compute_icao_check_digit(dob)
    exp = "300101"
    exp_chk = compute_icao_check_digit(exp)
    pers = "<<<<<<<<<<<<<<"
    pers_chk = "<"
    comp_data = f"{p_num}{p_chk}{dob}{dob_chk}{exp}{exp_chk}{pers}{pers_chk}"
    comp_chk = compute_icao_check_digit(comp_data)

    line2 = f"{p_num}{p_chk}USA{dob}{dob_chk}M{exp}{exp_chk}{pers}{pers_chk}{comp_chk}"

    cv2.putText(img, line1, (50, 850), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (10, 10, 10), 2)
    cv2.putText(img, line2, (50, 920), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (10, 10, 10), 2)

    return img


# ==========================================
# 1. SCANNER TESTS
# ==========================================
def test_order_points():
    pts = np.array([[300, 200], [50, 50], [50, 200], [300, 50]], dtype="float32")
    ordered = order_points(pts)
    assert np.array_equal(ordered[0], [50, 50])    # Top-Left
    assert np.array_equal(ordered[1], [300, 50])   # Top-Right
    assert np.array_equal(ordered[2], [300, 200])  # Bottom-Right
    assert np.array_equal(ordered[3], [50, 200])   # Bottom-Left


def test_four_point_transform():
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    pts = np.array([[100, 100], [700, 100], [700, 500], [100, 500]], dtype="float32")
    warped = four_point_transform(img, pts, target_width=710, target_height=500)
    assert warped.shape[0] == 500
    assert warped.shape[1] == 710


def test_scanner_with_valid_image():
    img = create_synthetic_passport_image()
    _, enc = cv2.imencode(".jpg", img)
    result = scan_passport(enc.tobytes(), force_fallback=True)
    assert result["cropped_bgr"] is not None
    assert result["preview_cropped_base64"].startswith("data:image/")
    assert result["dimensions"]["width"] > 0


def test_scanner_rejects_invalid_photo_without_fallback():
    # Random blank image with wrong aspect ratio (square 200x200)
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".jpg", img)
    with pytest.raises(ScannerError):
        scan_passport(enc.tobytes(), force_fallback=False)


# ==========================================
# 2. OCR & MRZ PARSER TESTS
# ==========================================
def test_icao_check_digit_calculation():
    # Standard ICAO Doc 9303 test cases
    # Example: number "L898902C3"
    # Weighting: 7, 3, 1, 7, 3, 1, 7, 3, 1
    # Check digit should compute deterministically
    cd = compute_icao_check_digit("L898902C3")
    assert cd.isdigit() and len(cd) == 1
    # Numbers with filler '<'
    assert compute_icao_check_digit("<<<<") == "0"


def test_parse_mrz_lines():
    line1 = "P<USADOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    line2 = "1234567897USA9001014M3001016<<<<<<<<<<<<<<4"
    res = parse_mrz_lines(line1, line2)
    assert res["document_type"] == "P"
    assert res["issuing_country"] == "USA"
    assert res["surname"] == "DOE"
    assert res["given_names"] == "JOHN"
    assert res["passport_number"] == "123456789"
    assert res["dob"] == "900101"
    assert res["sex"] == "M"
    assert res["expiry_date"] == "300101"


# ==========================================
# 3. VALIDATION & MOCK DATABASE TESTS
# ==========================================
def test_parse_mrz_date():
    dob = parse_mrz_date("950412", is_expiry=False)
    assert dob == date(1995, 4, 12)

    exp = parse_mrz_date("320815", is_expiry=True)
    assert exp == date(2032, 8, 15)

    assert parse_mrz_date("invalid") is None


def test_mock_blacklist_query():
    # L898902C3 is in mock_blacklist.csv
    hit = query_mock_blacklist("L898902C3")
    assert hit["matched"] is True
    assert hit["is_simulation"] is True

    clean = query_mock_blacklist("NONEXISTENT999")
    assert clean["matched"] is False


def test_validator_detects_mrz_checksum_and_date_issues():
    # Construct mock OCR output with bad checksum and past expiry
    mock_ocr = {
        "mrz": {
            "found": True,
            "fields": {
                "document_type": {"value": "P"},
                "issuing_country": {"value": "USA"},
                "surname": {"value": "SMITH"},
                "given_names": {"value": "ALICE"},
                "passport_number": {"value": "123456789", "expected_check": "7", "actual_check": "2"},
                "dob": {"value": "900101", "expected_check": "4", "actual_check": "4"},
                "expiry_date": {"value": "150101", "expected_check": "6", "actual_check": "6"}, # 2015 expired
            },
            "checksums": {
                "passport_number_valid": False,
                "dob_valid": True,
                "expiry_date_valid": True,
                "composite_valid": False,
                "all_valid": False,
            }
        },
        "viz": {"available": False},
        "cross_checks": []
    }

    val = validate_document(mock_ocr)
    assert val["passed"] is False
    codes = [i["code"] for i in val["issues"]]
    assert "CHECKSUM_PASSPORT_NUMBER_INVALID" in codes
    assert "PASSPORT_EXPIRED" in codes


# ==========================================
# 4. TAMPERING DETECTION TESTS
# ==========================================
def test_error_level_analysis():
    img = create_synthetic_passport_image()
    ela = compute_error_level_analysis(img, quality=90)
    assert "score" in ela
    assert "heatmap_base64" in ela
    assert ela["heatmap_base64"].startswith("data:image/")
    assert 0.0 <= ela["score"] <= 100.0


def test_exif_forensics():
    img = create_synthetic_passport_image()
    _, enc = cv2.imencode(".jpg", img)
    exif_res = analyze_exif_forensics(enc.tobytes())
    assert "score" in exif_res
    assert "flagged" in exif_res


def test_detect_tampering_ensemble():
    img = create_synthetic_passport_image()
    _, enc = cv2.imencode(".jpg", img)
    res = detect_tampering(img, enc.tobytes(), mrz_checksum_valid=True)
    assert 0.0 <= res["tamper_risk_score"] <= 100.0
    assert "signal_breakdown" in res
    assert "cnn_model" in res["signal_breakdown"]
    assert "error_level_analysis" in res["signal_breakdown"]
    assert "exif_forensics" in res["signal_breakdown"]


# ==========================================
# 5. FACE VERIFICATION TESTS
# ==========================================
def test_face_match_fallback():
    f1 = np.ones((100, 100, 3), dtype=np.uint8) * 128
    f2 = np.ones((100, 100, 3), dtype=np.uint8) * 128
    sim = fallback_feature_similarity(f1, f2)
    assert 0.0 <= sim <= 100.0


def test_compare_faces_without_selfie():
    img = create_synthetic_passport_image()
    res = compare_faces(img, live_selfie_bytes=None)
    assert res["performed"] is False
    assert "liveness_limitation_note" in res
