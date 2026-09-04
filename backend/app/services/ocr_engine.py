import re
import cv2
import numpy as np
from typing import Dict, Any, List, Optional
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from passporteye import read_mrz
except ImportError:
    read_mrz = None

try:
    from mrz.checker.td3 import TD3CodeChecker
except ImportError:
    TD3CodeChecker = None


def clean_mrz_line(line: str) -> str:
    """Cleans characters and replaces common OCR errors in MRZ lines."""
    line = line.strip().upper()
    # Replace whitespace with filler <
    line = re.sub(r'\s+', '<', line)
    # Remove any characters outside A-Z, 0-9, and <
    line = re.sub(r'[^A-Z0-9<]', '', line)
    return line


def parse_mrz_lines(line1: str, line2: str) -> Dict[str, Any]:
    """
    Parses standard ICAO Doc 9303 TD3 format MRZ lines (2 lines x 44 characters).
    Line 1: P<ISSLASTNAME<<FIRSTNAME<<<<<<<<<<<<<<<<<<<<<<
    Line 2: NUMBER<8ISSYYMMDD5SEXEXPIRYYYMMDD7PERSONAL<<<<<<5
    """
    line1 = clean_mrz_line(line1).ljust(44, '<')[:44]
    line2 = clean_mrz_line(line2).ljust(44, '<')[:44]

    doc_type = line1[0:2].replace('<', '')
    issuing_country = line1[2:5].replace('<', '')

    # Extract names
    name_portion = line1[5:44]
    name_parts = name_portion.split('<<')
    surname = name_parts[0].replace('<', ' ').strip() if len(name_parts) > 0 else ""
    given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""

    # Line 2 components
    passport_number = line2[0:9].replace('<', '')
    passport_num_check = line2[9]
    nationality = line2[10:13].replace('<', '')
    dob = line2[13:19].replace('<', '')
    dob_check = line2[19]
    sex = line2[20].replace('<', 'X')
    expiry_date = line2[21:27].replace('<', '')
    expiry_check = line2[27]
    personal_number = line2[28:42].replace('<', '')
    personal_check = line2[42]
    composite_check = line2[43]

    return {
        "document_type": doc_type or "P",
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "full_name": f"{given_names} {surname}".strip(),
        "passport_number": passport_number,
        "passport_number_check": passport_num_check,
        "nationality": nationality,
        "dob": dob,
        "dob_check": dob_check,
        "sex": sex,
        "expiry_date": expiry_date,
        "expiry_check": expiry_check,
        "personal_number": personal_number,
        "personal_check": personal_check,
        "composite_check": composite_check,
        "raw_lines": [line1, line2],
    }


def compute_icao_check_digit(data: str) -> str:
    """Calculates check digit according to ICAO Doc 9303 (weights 7, 3, 1)."""
    weights = [7, 3, 1]
    total = 0
    for idx, char in enumerate(data):
        if char == '<':
            val = 0
        elif char.isdigit():
            val = int(char)
        elif 'A' <= char <= 'Z':
            val = ord(char) - ord('A') + 10
        else:
            val = 0
        total += val * weights[idx % 3]
    return str(total % 10)


def extract_mrz_with_tesseract(image_bgr: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    Extracts MRZ directly by cropping the bottom 25% of the passport and running OCR.
    """
    if pytesseract is None:
        return None

    h, w = image_bgr.shape[:2]
    # MRZ occupies the bottom ~22-25% of the TD3 page
    mrz_roi = image_bgr[int(h * 0.72):h, 0:w]

    gray = cv2.cvtColor(mrz_roi, cv2.COLOR_BGR2GRAY)
    # Binarize with Otsu threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Tesseract configuration for MRZ (only uppercase, numbers, and '<')
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
    try:
        ocr_text = pytesseract.image_to_string(thresh, config=custom_config)
    except Exception:
        return None

    # Filter lines of length ~44 containing '<'
    candidate_lines = []
    for raw_line in ocr_text.splitlines():
        line = clean_mrz_line(raw_line)
        if len(line) >= 35 and '<' in line:
            candidate_lines.append(line)

    if len(candidate_lines) >= 2:
        return parse_mrz_lines(candidate_lines[-2], candidate_lines[-1])

    return None


def extract_mrz(image_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Extracts and parses the Machine-Readable Zone using PassportEye first, with Tesseract fallback.
    """
    result = None

    # Try PassportEye if installed
    if read_mrz is not None:
        try:
            # Convert BGR to RGB PIL image
            rgb_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_img)
            mrz_record = read_mrz(pil_img, save_mode=False)

            if mrz_record is not None:
                mrz_dict = mrz_record.to_dict()
                raw_text = getattr(mrz_record, "raw_text", "")
                raw_lines = [clean_mrz_line(l) for l in raw_text.splitlines() if clean_mrz_line(l)]
                if len(raw_lines) >= 2:
                    result = parse_mrz_lines(raw_lines[-2], raw_lines[-1])
                else:
                    # Fallback to field mapping from PassportEye
                    result = {
                        "document_type": mrz_dict.get("type", "P"),
                        "issuing_country": mrz_dict.get("country", ""),
                        "surname": mrz_dict.get("surname", ""),
                        "given_names": mrz_dict.get("names", ""),
                        "full_name": f"{mrz_dict.get('names', '')} {mrz_dict.get('surname', '')}".strip(),
                        "passport_number": mrz_dict.get("number", ""),
                        "passport_number_check": mrz_dict.get("check_number", ""),
                        "nationality": mrz_dict.get("nationality", ""),
                        "dob": mrz_dict.get("date_of_birth", ""),
                        "dob_check": mrz_dict.get("check_date_of_birth", ""),
                        "sex": mrz_dict.get("sex", ""),
                        "expiry_date": mrz_dict.get("expiration_date", ""),
                        "expiry_check": mrz_dict.get("check_expiration_date", ""),
                        "personal_number": mrz_dict.get("personal_number", ""),
                        "personal_check": mrz_dict.get("check_personal_number", ""),
                        "composite_check": mrz_dict.get("check_composite", ""),
                        "raw_lines": raw_lines or ["", ""],
                    }
        except Exception:
            result = None

    # Fallback to direct Tesseract OCR if PassportEye didn't find MRZ
    if result is None:
        result = extract_mrz_with_tesseract(image_bgr)

    # If still not found, return empty placeholder structure
    if result is None:
        return {
            "found": False,
            "fields": {},
            "raw_lines": [],
            "message": "No valid MRZ detected on bottom region of passport."
        }

    # Verify check digits
    pass_num = result.get("passport_number", "")
    pass_check = result.get("passport_number_check", "")
    dob = result.get("dob", "")
    dob_check = result.get("dob_check", "")
    exp = result.get("expiry_date", "")
    exp_check = result.get("expiry_check", "")

    pass_valid = compute_icao_check_digit(pass_num) == pass_check if pass_check else False
    dob_valid = compute_icao_check_digit(dob) == dob_check if dob_check else False
    exp_valid = compute_icao_check_digit(exp) == exp_check if exp_check else False

    # Composite check over: passport_no + pass_check + dob + dob_check + exp + exp_check + personal + personal_check
    comp_str = f"{pass_num.ljust(9, '<')}{pass_check}{dob}{dob_check}{exp}{exp_check}{result.get('personal_number', '').ljust(14, '<')}{result.get('personal_check', '<')}"
    comp_expected = compute_icao_check_digit(comp_str)
    comp_valid = comp_expected == result.get("composite_check", "") if result.get("composite_check") else (pass_valid and dob_valid and exp_valid)

    all_checksums_pass = pass_valid and dob_valid and exp_valid

    return {
        "found": True,
        "fields": {
            "document_type": {"value": result.get("document_type", "P"), "source": "mrz", "confidence": 0.99},
            "issuing_country": {"value": result.get("issuing_country", ""), "source": "mrz", "confidence": 0.98},
            "surname": {"value": result.get("surname", ""), "source": "mrz", "confidence": 0.95},
            "given_names": {"value": result.get("given_names", ""), "source": "mrz", "confidence": 0.95},
            "full_name": {"value": result.get("full_name", ""), "source": "mrz", "confidence": 0.95},
            "passport_number": {
                "value": result.get("passport_number", ""),
                "source": "mrz",
                "confidence": 0.99 if pass_valid else 0.60,
                "checksum_valid": pass_valid,
                "expected_check": compute_icao_check_digit(pass_num),
                "actual_check": pass_check,
            },
            "nationality": {"value": result.get("nationality", ""), "source": "mrz", "confidence": 0.98},
            "dob": {
                "value": result.get("dob", ""),
                "source": "mrz",
                "confidence": 0.99 if dob_valid else 0.60,
                "checksum_valid": dob_valid,
                "expected_check": compute_icao_check_digit(dob),
                "actual_check": dob_check,
            },
            "sex": {"value": result.get("sex", "X"), "source": "mrz", "confidence": 0.97},
            "expiry_date": {
                "value": result.get("expiry_date", ""),
                "source": "mrz",
                "confidence": 0.99 if exp_valid else 0.60,
                "checksum_valid": exp_valid,
                "expected_check": compute_icao_check_digit(exp),
                "actual_check": exp_check,
            },
        },
        "raw_lines": result.get("raw_lines", []),
        "checksums": {
            "passport_number_valid": pass_valid,
            "dob_valid": dob_valid,
            "expiry_date_valid": exp_valid,
            "composite_valid": comp_valid,
            "all_valid": all_checksums_pass,
        }
    }


def extract_viz_text(image_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Extracts text from the Visual Inspection Zone (upper 70% of the document page).
    Cross-checks against MRZ fields.
    """
    if pytesseract is None:
        return {"available": False, "raw_text": "", "fields": {}}

    h, w = image_bgr.shape[:2]
    # Crop VIZ (exclude bottom 30% MRZ and left 30% photo area)
    viz_roi = image_bgr[int(h * 0.10):int(h * 0.72), int(w * 0.32):int(w * 0.98)]

    gray = cv2.cvtColor(viz_roi, cv2.COLOR_BGR2GRAY)
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    try:
        raw_text = pytesseract.image_to_string(enhanced)
    except Exception:
        raw_text = ""

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    return {
        "available": True,
        "raw_text": raw_text,
        "extracted_lines": lines,
    }


def extract_document_fields(image_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Master OCR orchestrator: extracts MRZ and VIZ, performs cross-checking.
    """
    mrz_data = extract_mrz(image_bgr)
    viz_data = extract_viz_text(image_bgr)

    # Cross-check VIZ against MRZ
    cross_checks = []
    if mrz_data.get("found") and viz_data.get("available"):
        viz_text_upper = viz_data.get("raw_text", "").upper()
        surname = mrz_data["fields"].get("surname", {}).get("value", "").upper()
        pass_num = mrz_data["fields"].get("passport_number", {}).get("value", "").upper()

        if surname and len(surname) >= 3:
            surname_matched = surname in viz_text_upper
            cross_checks.append({
                "field": "surname",
                "mrz_value": surname,
                "viz_match": surname_matched,
                "note": "Surname appears in visual inspection zone" if surname_matched else "Surname not detected in visual inspection zone (potential mismatch or low OCR clarity)"
            })

        if pass_num and len(pass_num) >= 5:
            pass_matched = pass_num in viz_text_upper
            cross_checks.append({
                "field": "passport_number",
                "mrz_value": pass_num,
                "viz_match": pass_matched,
                "note": "Passport number matched in visual inspection zone" if pass_matched else "Passport number not detected in visual zone"
            })

    return {
        "mrz": mrz_data,
        "viz": viz_data,
        "cross_checks": cross_checks,
        "all_checksums_pass": mrz_data.get("checksums", {}).get("all_valid", False) if mrz_data.get("found") else False
    }
