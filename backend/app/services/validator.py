import csv
import os
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from ..config import MOCK_BLACKLIST_PATH

# ICAO Doc 9303 / National Passport Format Regular Expressions
COUNTRY_PASSPORT_PATTERNS = {
    "USA": r'^[0-9]{9}$',                # 9 digits
    "GBR": r'^[0-9]{9}$',                # 9 digits
    "IND": r'^[A-Z][0-9]{7}$',           # 1 uppercase letter + 7 digits
    "CAN": r'^[A-Z]{2}[0-9]{6}$',        # 2 letters + 6 digits
    "AUS": r'^[A-Z][0-9]{7}$',           # 1 letter + 7 digits
    "DEU": r'^[CFGHJKLMNPRTVWXYZ0-9]{9}$', # German e-passport serial format
    "FRA": r'^[0-9]{2}[A-Z]{2}[0-9]{5}$',# 2 digits + 2 letters + 5 digits
    "ITA": r'^[A-Z]{2}[0-9]{7}$',        # 2 letters + 7 digits
    "ESP": r'^[A-Z]{3}[0-9]{6}$',        # 3 letters + 6 digits
    "JPN": r'^[A-Z]{2}[0-9]{7}$',        # 2 letters + 7 digits
}


def parse_mrz_date(yy_mm_dd: str, is_expiry: bool = False) -> Optional[date]:
    """
    Parses YYMMDD formatted date into a datetime.date object.
    Uses century heuristics:
    - For expiry dates: 00-79 is 2000s, 80-99 is 1900s.
    - For DOB: current_year % 100 cut-off (usually <= current_yy is 2000s, > current_yy is 1900s).
    """
    if not yy_mm_dd or len(yy_mm_dd) != 6 or not yy_mm_dd.isdigit():
        return None

    try:
        yy = int(yy_mm_dd[0:2])
        mm = int(yy_mm_dd[2:4])
        dd = int(yy_mm_dd[4:6])

        current_year = date.today().year
        current_yy = current_year % 100

        if is_expiry:
            # Expiry date is usually in the 2000s
            full_year = 2000 + yy if yy <= 80 else 1900 + yy
        else:
            # DOB logic
            full_year = 2000 + yy if yy <= current_yy else 1900 + yy

        return date(full_year, mm, dd)
    except ValueError:
        return None


def query_mock_blacklist(passport_number: str, surname: str = "", given_names: str = "") -> Dict[str, Any]:
    """
    Queries local mock database for simulated Interpol Stolen/Lost Travel Documents (SLTD)
    or simulated border watchlists. Clearly labeled as mock stand-in.
    """
    clean_pass = passport_number.strip().upper() if passport_number else ""
    surname_clean = surname.strip().upper() if surname else ""

    if not os.path.exists(MOCK_BLACKLIST_PATH) or not clean_pass:
        return {
            "matched": False,
            "database_source": "SIMULATED_INTERPOL_SLTD_STANDIN",
            "is_simulation": True,
            "record": None,
            "note": "Local mock database initialized (simulation only; no live connection)"
        }

    try:
        with open(MOCK_BLACKLIST_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                db_pass = row.get("passport_number", "").strip().upper()
                db_surname = row.get("surname", "").strip().upper()

                if db_pass and db_pass == clean_pass:
                    return {
                        "matched": True,
                        "database_source": row.get("category", "INTERPOL_SLTD_SIMULATED"),
                        "is_simulation": True,
                        "reason": row.get("reason", "Flagged in simulated register"),
                        "record": row,
                        "note": "SIMULATED HIT: Document matched a demo test record in the mock watchlist."
                    }
                elif surname_clean and db_surname and surname_clean == db_surname:
                    return {
                        "matched": True,
                        "database_source": row.get("category", "NATIONAL_WATCHLIST_SIMULATED"),
                        "is_simulation": True,
                        "reason": f"Name match: {row.get('reason')}",
                        "record": row,
                        "note": "SIMULATED HIT: Traveler name matched a demo record in the mock watchlist."
                    }
    except Exception as e:
        return {
            "matched": False,
            "database_source": "SIMULATED_INTERPOL_SLTD_STANDIN",
            "is_simulation": True,
            "error": str(e),
            "note": "Error reading mock blacklist"
        }

    return {
        "matched": False,
        "database_source": "SIMULATED_INTERPOL_SLTD_STANDIN",
        "is_simulation": True,
        "record": None,
        "note": "No match found in simulated watchlist database."
    }


def validate_document(ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs full document validation rules on OCR & MRZ output:
    1. MRZ checksum integrity
    2. Date logic & chronology
    3. Country code & passport format regex
    4. Name charset verification
    5. Mock database watchlist lookup
    """
    issues: List[Dict[str, Any]] = []
    checks_run: List[str] = []

    mrz_data = ocr_result.get("mrz", {})
    mrz_found = mrz_data.get("found", False)
    fields = mrz_data.get("fields", {})

    passport_num = fields.get("passport_number", {}).get("value", "")
    country_code = fields.get("issuing_country", {}).get("value", "")
    nationality = fields.get("nationality", {}).get("value", "")
    dob_str = fields.get("dob", {}).get("value", "")
    expiry_str = fields.get("expiry_date", {}).get("value", "")
    surname = fields.get("surname", {}).get("value", "")
    given_names = fields.get("given_names", {}).get("value", "")

    # 1. MRZ Found Check
    checks_run.append("MRZ Presence")
    if not mrz_found:
        issues.append({
            "type": "error",
            "code": "MRZ_NOT_FOUND",
            "message": "Standard TD3 Machine Readable Zone was not detected or unreadable."
        })

    # 2. Checksum Validation
    checks_run.append("MRZ Checksums (ICAO 7-3-1)")
    checksums = mrz_data.get("checksums", {})
    if mrz_found:
        if not checksums.get("passport_number_valid", False):
            issues.append({
                "type": "error",
                "code": "CHECKSUM_PASSPORT_NUMBER_INVALID",
                "message": f"Passport number check digit mismatch (Computed: {fields.get('passport_number', {}).get('expected_check')}, Actual: {fields.get('passport_number', {}).get('actual_check')}). Strong tampering signal."
            })
        if not checksums.get("dob_valid", False):
            issues.append({
                "type": "error",
                "code": "CHECKSUM_DOB_INVALID",
                "message": f"Date of birth check digit mismatch. Possible altered birth date."
            })
        if not checksums.get("expiry_date_valid", False):
            issues.append({
                "type": "error",
                "code": "CHECKSUM_EXPIRY_INVALID",
                "message": f"Expiry date check digit mismatch. Possible altered expiration date."
            })
        if not checksums.get("composite_valid", False):
            issues.append({
                "type": "error",
                "code": "CHECKSUM_COMPOSITE_INVALID",
                "message": "MRZ composite check digit validation failed."
            })

    # 3. Date Chronology & Validity
    checks_run.append("Date Chronology & Expiration")
    today = date.today()
    dob_date = parse_mrz_date(dob_str, is_expiry=False)
    expiry_date = parse_mrz_date(expiry_str, is_expiry=True)

    if dob_date:
        if dob_date > today:
            issues.append({
                "type": "error",
                "code": "DATE_DOB_IN_FUTURE",
                "message": f"Date of birth {dob_date.isoformat()} cannot be in the future."
            })
        else:
            age = (today - dob_date).days // 365
            if age > 120:
                issues.append({
                    "type": "warning",
                    "code": "DATE_AGE_ANOMALY",
                    "message": f"Calculated traveler age is {age} years, which is unusually high."
                })
    elif dob_str:
        issues.append({
            "type": "warning",
            "code": "DATE_DOB_PARSE_FAIL",
            "message": f"Unable to parse date of birth '{dob_str}' into a valid calendar date."
        })

    if expiry_date:
        if expiry_date < today:
            issues.append({
                "type": "error",
                "code": "PASSPORT_EXPIRED",
                "message": f"Passport expired on {expiry_date.isoformat()} and is invalid for international travel."
            })
        # 6-month validity rule warning common to international flights
        elif (expiry_date - today).days < 180:
            issues.append({
                "type": "warning",
                "code": "PASSPORT_EXPIRING_SOON",
                "message": f"Passport expires within 6 months ({expiry_date.isoformat()}). May violate immigration minimum validity rules."
            })

        if dob_date and expiry_date:
            validity_span_years = (expiry_date - dob_date).days / 365.25
            if validity_span_years <= 0:
                issues.append({
                    "type": "error",
                    "code": "DATE_CHRONOLOGY_INVERTED",
                    "message": "Expiry date precedes date of birth."
                })
    elif expiry_str:
        issues.append({
            "type": "warning",
            "code": "DATE_EXPIRY_PARSE_FAIL",
            "message": f"Unable to parse expiry date '{expiry_str}' into a valid calendar date."
        })

    # 4. Issuing Country Format & Regex
    checks_run.append("Issuing State & Number Format")
    if country_code:
        if not re.match(r'^[A-Z]{3}$', country_code):
            issues.append({
                "type": "error",
                "code": "COUNTRY_CODE_INVALID",
                "message": f"Country code '{country_code}' is not a standard 3-letter ICAO code."
            })
        elif country_code in COUNTRY_PASSPORT_PATTERNS and passport_num:
            pattern = COUNTRY_PASSPORT_PATTERNS[country_code]
            if not re.match(pattern, passport_num):
                issues.append({
                    "type": "warning",
                    "code": "PASSPORT_NUMBER_FORMAT_MISMATCH",
                    "message": f"Passport number '{passport_num}' does not match expected format for {country_code} (Regex: {pattern})."
                })

    # 5. Name Charset Validation
    checks_run.append("Name Character Set")
    if surname and re.search(r'[0-9]', surname):
        issues.append({
            "type": "error",
            "code": "NAME_CONTAINS_NUMBERS",
            "message": f"Surname '{surname}' contains numeric digits."
        })
    if given_names and re.search(r'[0-9]', given_names):
        issues.append({
            "type": "error",
            "code": "NAME_CONTAINS_NUMBERS",
            "message": f"Given name '{given_names}' contains numeric digits."
        })

    # 6. Mock Blacklist / Watchlist Lookup
    checks_run.append("Mock Stolen / Watchlist Database")
    mock_db_result = query_mock_blacklist(passport_num, surname=surname, given_names=given_names)
    if mock_db_result.get("matched"):
        issues.append({
            "type": "error",
            "code": "MOCK_BLACKLIST_MATCH",
            "message": f"DOCUMENT ALERT ({mock_db_result.get('database_source')}): {mock_db_result.get('reason')} [DEMO SIMULATION]"
        })

    passed = not any(issue["type"] == "error" for issue in issues)

    return {
        "passed": passed,
        "issues": issues,
        "checks_run": checks_run,
        "mock_db_result": mock_db_result,
        "summary": "Validation passed with no critical errors" if passed else f"Validation failed with {len([i for i in issues if i['type'] == 'error'])} error(s)"
    }
