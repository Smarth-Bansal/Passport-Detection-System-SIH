from .scanner import scan_passport, ScannerError
from .ocr_engine import (
    extract_document_fields,
    compute_icao_check_digit,
    compute_icao_breakdown,
    parse_weights_string,
)
from .validator import validate_document
from .tamper_detector import detect_tampering
from .face_match import compare_faces

__all__ = [
    "scan_passport",
    "ScannerError",
    "extract_document_fields",
    "compute_icao_check_digit",
    "compute_icao_breakdown",
    "parse_weights_string",
    "validate_document",
    "detect_tampering",
    "compare_faces",
]

