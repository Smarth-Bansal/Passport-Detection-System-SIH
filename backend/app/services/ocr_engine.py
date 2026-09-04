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


DIGIT_REPLACEMENTS = {
    'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'B': '8', 'G': '6'
}
LETTER_REPLACEMENTS = {
    '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B', '6': 'G'
}


def parse_weights_string(w_str: Optional[str]) -> List[int]:
    """Parses a comma or space separated list of integer weights."""
    if not w_str:
        return [7, 3, 1]
    try:
        parts = re.split(r'[, \-_]+', w_str.strip())
        weights = [int(p) for p in parts if p.isdigit()]
        return weights if len(weights) > 0 else [7, 3, 1]
    except Exception:
        return [7, 3, 1]


def force_digits(text: str) -> str:
    """Replaces OCR letter misreadings in strictly numeric fields."""
    return ''.join(c if c.isdigit() else DIGIT_REPLACEMENTS.get(c, '0' if c != '<' else '<') for c in text)


def force_letters(text: str) -> str:
    """Replaces OCR digit misreadings in strictly alphabetic fields."""
    return ''.join(c if c.isalpha() else LETTER_REPLACEMENTS.get(c, '<' if c == '<' else 'X') for c in text)


def clean_mrz_line(line: str) -> str:
    """Cleans characters and replaces common OCR errors in MRZ lines."""
    line = line.strip().upper()
    line = re.sub(r'\s+', '<', line)
    line = re.sub(r'[^A-Z0-9<]', '', line)
    return line


def clean_td3_line2(l2: str) -> str:
    """
    Contextually cleans TD3 Line 2 according to ICAO Doc 9303 field types.
    Pos 0-8: Passport Number
    Pos 9: Passport Check Digit (Numeric)
    Pos 10-12: Nationality (3 Letters, e.g. 1ND -> IND)
    Pos 13-18: Date of Birth YYMMDD (Numeric)
    Pos 19: DOB Check Digit (Numeric)
    Pos 20: Sex (M, F, X, <)
    Pos 21-26: Expiry Date YYMMDD (Numeric)
    Pos 27: Expiry Check Digit (Numeric)
    Pos 28-41: Optional / Personal Number
    Pos 42: Personal Check Digit (Numeric or <)
    Pos 43: Composite Check Digit (Numeric)
    """
    l2 = re.sub(r'[^A-Z0-9<]', '', l2.strip().upper()).ljust(44, '<')[:44]
    p_num = l2[0:9]
    p_chk = force_digits(l2[9])
    nat = force_letters(l2[10:13])
    dob = force_digits(l2[13:19])
    dob_chk = force_digits(l2[19])
    sex = l2[20] if l2[20] in ('M', 'F', 'X', '<') else '<'
    exp = force_digits(l2[21:27])
    exp_chk = force_digits(l2[27])
    pers = l2[28:42]
    pers_chk = force_digits(l2[42]) if l2[42] != '<' else '<'
    comp_chk = force_digits(l2[43])
    return f"{p_num}{p_chk}{nat}{dob}{dob_chk}{sex}{exp}{exp_chk}{pers}{pers_chk}{comp_chk}"


def clean_td3_line1(l1: str, nat_hint: str = "") -> str:
    """
    Contextually cleans TD3 Line 1 according to ICAO Doc 9303.
    Resolves OCR-B chevron misreadings (e.g. 'K' or 'C' as '<' fillers)
    and delimiter glitches (e.g. 'P<I<ND' -> 'P<IND').
    """
    l1 = re.sub(r'[^A-Z0-9<]', '', l1.strip().upper())
    # Replace trailing sequence of K, X, <, E, Q, C with chevrons <
    l1 = re.sub(r'[K<XEQCS(]{3,}$', lambda m: '<' * len(m.group(0)), l1)

    country = nat_hint if len(nat_hint) == 3 else "XXX"
    rem = ""

    if l1.startswith("P"):
        prefix = l1[:8]
        letters = [c for c in prefix if c.isalpha()]
        if len(letters) >= 4 and letters[0] == 'P':
            country = ''.join(letters[1:4])
            idx = prefix.rfind(country[-1])
            rem = l1[idx + 1:]
        elif nat_hint and len(nat_hint) == 3:
            country = nat_hint
            rem = l1[5:] if len(l1) > 5 else ""
        else:
            country = force_letters(l1[2:5].replace('<', ''))[:3]
            rem = l1[5:] if len(l1) > 5 else ""
    else:
        rem = l1[5:] if len(l1) > 5 else ""

    # Clean name portion
    rem = re.sub(r'<<([A-Z]+)[K<]+', r'<<\1<', rem)
    rem = re.sub(r'K{2,}', lambda m: '<' * len(m.group(0)), rem)
    rem = re.sub(r'[K<XEQCS(]+$', lambda m: '<' * len(m.group(0)), rem)

    return f"P<{country}{rem}".ljust(44, '<')[:44]


def compute_icao_check_digit(data: str, weights: Optional[List[int]] = None, modulo: int = 10) -> str:
    """Calculates check digit according to ICAO Doc 9303 (default weights 7, 3, 1 mod 10)."""
    if not weights:
        weights = [7, 3, 1]
    w_len = len(weights)
    mod = modulo if modulo and modulo > 0 else 10
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
        total += val * weights[idx % w_len]
    return str(total % mod)


def compute_icao_breakdown(
    data: str,
    weights: Optional[List[int]] = None,
    modulo: int = 10,
    expected_check: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates detailed step-by-step arithmetic breakdown for interactive inspection."""
    if not weights:
        weights = [7, 3, 1]
    w_len = len(weights)
    mod = modulo if modulo and modulo > 0 else 10

    steps = []
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

        w = weights[idx % w_len]
        product = val * w
        total += product
        steps.append({
            "pos": idx + 1,
            "char": char,
            "val": val,
            "weight": w,
            "product": product,
            "running_sum": total,
        })

    computed = str(total % mod)
    is_valid = (computed == str(expected_check).strip()) if expected_check is not None and expected_check != "" else None

    return {
        "input_string": data,
        "weights": weights,
        "modulo": mod,
        "total_sum": total,
        "computed_check_digit": computed,
        "expected_check_digit": expected_check,
        "is_valid": is_valid,
        "formula_expression": f"(∑ char_val × weight) mod {mod} = {total} mod {mod} = {computed}",
        "steps": steps,
    }


def parse_mrz_lines(
    line1: str,
    line2: str,
    weights: Optional[List[int]] = None,
    modulo: int = 10,
) -> Dict[str, Any]:
    """
    Parses and verifies standard ICAO Doc 9303 TD3 format MRZ lines.
    Applies contextual OCR cleaning to both lines.
    """
    cleaned_l2 = clean_td3_line2(line2)
    nat_hint = cleaned_l2[10:13]
    cleaned_l1 = clean_td3_line1(line1, nat_hint=nat_hint)

    doc_type = cleaned_l1[0:2].replace('<', '')
    issuing_country = cleaned_l1[2:5].replace('<', '')

    # Extract names
    name_portion = cleaned_l1[5:44]
    name_parts = name_portion.split('<<')
    surname = name_parts[0].replace('<', ' ').strip() if len(name_parts) > 0 else ""
    given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""

    # Line 2 components
    passport_number = cleaned_l2[0:9].replace('<', '')
    passport_num_check = cleaned_l2[9]
    nationality = cleaned_l2[10:13].replace('<', '')
    dob = cleaned_l2[13:19].replace('<', '')
    dob_check = cleaned_l2[19]
    sex = cleaned_l2[20].replace('<', 'X')
    expiry_date = cleaned_l2[21:27].replace('<', '')
    expiry_check = cleaned_l2[27]
    personal_number = cleaned_l2[28:42].replace('<', '')
    personal_check = cleaned_l2[42]
    composite_check = cleaned_l2[43]

    # Validate check digits with specified weights
    pass_num_raw = cleaned_l2[0:9]
    expected_pass_chk = compute_icao_check_digit(pass_num_raw, weights=weights, modulo=modulo)
    pass_valid = expected_pass_chk == passport_num_check

    expected_dob_chk = compute_icao_check_digit(dob, weights=weights, modulo=modulo)
    dob_valid = expected_dob_chk == dob_check

    expected_exp_chk = compute_icao_check_digit(expiry_date, weights=weights, modulo=modulo)
    exp_valid = expected_exp_chk == expiry_check

    # Composite check over: pass_num(9) + pass_chk(1) + dob(6) + dob_chk(1) + exp(6) + exp_chk(1) + personal(14) + personal_chk(1)
    comp_str = f"{pass_num_raw}{passport_num_check}{dob}{dob_check}{expiry_date}{expiry_check}{cleaned_l2[28:42]}{personal_check}"
    expected_comp_chk = compute_icao_check_digit(comp_str, weights=weights, modulo=modulo)
    comp_valid = expected_comp_chk == composite_check

    all_valid = pass_valid and dob_valid and exp_valid and comp_valid

    return {
        "document_type": doc_type or "P",
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "full_name": f"{given_names} {surname}".strip() if given_names or surname else "",
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
        "raw_lines": [cleaned_l1, cleaned_l2],
        "original_lines": [clean_mrz_line(line1), clean_mrz_line(line2)],
        "checksum_results": {
            "passport_number_valid": pass_valid,
            "dob_valid": dob_valid,
            "expiry_date_valid": exp_valid,
            "composite_valid": comp_valid,
            "all_valid": all_valid,
        },
        "expected_checks": {
            "passport_number": expected_pass_chk,
            "dob": expected_dob_chk,
            "expiry_date": expected_exp_chk,
            "composite": expected_comp_chk,
        }
    }


def extract_mrz_with_tesseract(
    image_bgr: np.ndarray,
    weights: Optional[List[int]] = None,
    modulo: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Multi-pass MRZ extraction using Blackhat morphology, CLAHE, and Otsu binarization.
    """
    if pytesseract is None:
        return None

    h, w = image_bgr.shape[:2]
    # MRZ occupies bottom ~26% of TD3 page
    mrz_roi = image_bgr[int(h * 0.70):h, 0:w]
    gray = cv2.cvtColor(mrz_roi, cv2.COLOR_BGR2GRAY)

    variants: List[np.ndarray] = []

    # 1. Morphological Blackhat (superb for isolating dark OCR-B text on patterned security paper)
    try:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        _, bh_thresh = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        variants.append(bh_thresh)
    except Exception:
        pass

    # 2. CLAHE + Otsu
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl_gray = clahe.apply(gray)
        _, cl_thresh = cv2.threshold(cl_gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        variants.append(cl_thresh)
    except Exception:
        pass

    # 3. Adaptive Gaussian
    try:
        ag_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
        variants.append(ag_thresh)
    except Exception:
        pass

    # 4. Standard Otsu
    _, std_thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    variants.append(std_thresh)

    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'

    best_result = None
    best_score = -1

    for img_var in variants:
        try:
            ocr_text = pytesseract.image_to_string(img_var, config=custom_config)
        except Exception:
            continue

        candidate_lines = []
        for raw_line in ocr_text.splitlines():
            line = clean_mrz_line(raw_line)
            if len(line) >= 30 and '<' in line:
                candidate_lines.append(line)

        if len(candidate_lines) >= 2:
            l1 = candidate_lines[-2]
            l2 = candidate_lines[-1]
            parsed = parse_mrz_lines(l1, l2, weights=weights, modulo=modulo)
            chks = parsed["checksum_results"]
            # Score this variant
            score = 0
            if chks.get("passport_number_valid"):
                score += 3
            if chks.get("dob_valid"):
                score += 3
            if chks.get("expiry_date_valid"):
                score += 3
            if chks.get("composite_valid"):
                score += 5
            if len(parsed.get("issuing_country", "")) == 3:
                score += 2

            if score > best_score:
                best_score = score
                best_result = parsed
                if chks.get("all_valid"):
                    break

    return best_result


def extract_mrz(
    image_bgr: np.ndarray,
    manual_line1: Optional[str] = None,
    manual_line2: Optional[str] = None,
    weights: Optional[List[int]] = None,
    modulo: int = 10,
) -> Dict[str, Any]:
    """
    Extracts and parses Machine-Readable Zone with multi-pass OCR and manual override support.
    """
    # 1. Manual Line Override if supplied by user
    if manual_line1 and manual_line2:
        parsed = parse_mrz_lines(manual_line1, manual_line2, weights=weights, modulo=modulo)
        return {
            "found": True,
            "fields": {
                "document_type": {"value": parsed["document_type"], "source": "manual", "confidence": 1.0},
                "issuing_country": {"value": parsed["issuing_country"], "source": "manual", "confidence": 1.0},
                "surname": {"value": parsed["surname"], "source": "manual", "confidence": 1.0},
                "given_names": {"value": parsed["given_names"], "source": "manual", "confidence": 1.0},
                "full_name": {"value": parsed["full_name"], "source": "manual", "confidence": 1.0},
                "passport_number": {
                    "value": parsed["passport_number"],
                    "source": "manual",
                    "confidence": 1.0,
                    "checksum_valid": parsed["checksum_results"]["passport_number_valid"],
                    "expected_check": parsed["expected_checks"]["passport_number"],
                    "actual_check": parsed["passport_number_check"],
                },
                "nationality": {"value": parsed["nationality"], "source": "manual", "confidence": 1.0},
                "dob": {
                    "value": parsed["dob"],
                    "source": "manual",
                    "confidence": 1.0,
                    "checksum_valid": parsed["checksum_results"]["dob_valid"],
                    "expected_check": parsed["expected_checks"]["dob"],
                    "actual_check": parsed["dob_check"],
                },
                "sex": {"value": parsed["sex"], "source": "manual", "confidence": 1.0},
                "expiry_date": {
                    "value": parsed["expiry_date"],
                    "source": "manual",
                    "confidence": 1.0,
                    "checksum_valid": parsed["checksum_results"]["expiry_date_valid"],
                    "expected_check": parsed["expected_checks"]["expiry_date"],
                    "actual_check": parsed["expiry_check"],
                },
            },
            "raw_lines": parsed["raw_lines"],
            "checksums": parsed["checksum_results"],
            "formula_used": {"weights": weights or [7, 3, 1], "modulo": modulo},
            "source": "manual_officer_override"
        }

    result = None

    # 2. Try PassportEye if installed
    if read_mrz is not None:
        try:
            rgb_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_img)
            mrz_record = read_mrz(pil_img, save_mode=False)

            if mrz_record is not None:
                raw_text = getattr(mrz_record, "raw_text", "")
                raw_lines = [clean_mrz_line(l) for l in raw_text.splitlines() if clean_mrz_line(l)]
                if len(raw_lines) >= 2:
                    result = parse_mrz_lines(raw_lines[-2], raw_lines[-1], weights=weights, modulo=modulo)
        except Exception:
            result = None

    # 3. Fallback to advanced multi-pass Tesseract OCR if PassportEye failed or checksums didn't validate
    if result is None or not result.get("checksum_results", {}).get("all_valid"):
        tess_res = extract_mrz_with_tesseract(image_bgr, weights=weights, modulo=modulo)
        if tess_res is not None:
            # If PassportEye had no result or Tesseract found all valid checksums, prefer Tesseract
            if result is None or tess_res.get("checksum_results", {}).get("all_valid"):
                result = tess_res

    # If still not found
    if result is None:
        return {
            "found": False,
            "fields": {},
            "raw_lines": [],
            "checksums": {"all_valid": False},
            "message": "No valid MRZ detected on bottom region of passport."
        }

    chks = result.get("checksum_results", {})
    exp_chks = result.get("expected_checks", {})

    return {
        "found": True,
        "fields": {
            "document_type": {"value": result["document_type"], "source": "mrz", "confidence": 0.99},
            "issuing_country": {"value": result["issuing_country"], "source": "mrz", "confidence": 0.98},
            "surname": {"value": result["surname"], "source": "mrz", "confidence": 0.95},
            "given_names": {"value": result["given_names"], "source": "mrz", "confidence": 0.95},
            "full_name": {"value": result["full_name"], "source": "mrz", "confidence": 0.95},
            "passport_number": {
                "value": result["passport_number"],
                "source": "mrz",
                "confidence": 0.99 if chks.get("passport_number_valid") else 0.60,
                "checksum_valid": chks.get("passport_number_valid", False),
                "expected_check": exp_chks.get("passport_number", ""),
                "actual_check": result["passport_number_check"],
            },
            "nationality": {"value": result["nationality"], "source": "mrz", "confidence": 0.98},
            "dob": {
                "value": result["dob"],
                "source": "mrz",
                "confidence": 0.99 if chks.get("dob_valid") else 0.60,
                "checksum_valid": chks.get("dob_valid", False),
                "expected_check": exp_chks.get("dob", ""),
                "actual_check": result["dob_check"],
            },
            "sex": {"value": result["sex"], "source": "mrz", "confidence": 0.97},
            "expiry_date": {
                "value": result["expiry_date"],
                "source": "mrz",
                "confidence": 0.99 if chks.get("expiry_date_valid") else 0.60,
                "checksum_valid": chks.get("expiry_date_valid", False),
                "expected_check": exp_chks.get("expiry_date", ""),
                "actual_check": result["expiry_check"],
            },
        },
        "raw_lines": result["raw_lines"],
        "checksums": chks,
        "formula_used": {"weights": weights or [7, 3, 1], "modulo": modulo},
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


def extract_document_fields(
    image_bgr: np.ndarray,
    manual_line1: Optional[str] = None,
    manual_line2: Optional[str] = None,
    weights: Optional[List[int]] = None,
    modulo: int = 10,
) -> Dict[str, Any]:
    """
    Master OCR orchestrator: extracts MRZ and VIZ, performs cross-checking.
    Supports manual MRZ override and custom ICAO formula weights.
    """
    mrz_data = extract_mrz(
        image_bgr,
        manual_line1=manual_line1,
        manual_line2=manual_line2,
        weights=weights,
        modulo=modulo,
    )
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
