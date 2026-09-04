import base64
import os
import math
from typing import Dict, Any, Optional, Tuple, List

import cv2
import numpy as np

try:
    import face_recognition
except ImportError:
    face_recognition = None

try:
    import dlib
except ImportError:
    dlib = None

try:
    from ..config import FACE_MATCH_MISMATCH_MAX, FACE_MATCH_PASS_MIN
except ImportError:
    FACE_MATCH_MISMATCH_MAX = 40.0
    FACE_MATCH_PASS_MIN = 55.0



def image_to_base64(img_bgr: np.ndarray, quality: int = 90) -> str:
    """Converts a BGR OpenCV image to a base64 encoded data URL."""
    success, buffer = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        return ""
    b64_str = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"


def find_face_with_face_recognition(image_rgb: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Locates the primary face using face_recognition (HOG or CNN).
    Returns (x, y, w, h) in standard pixel coordinates.
    """
    if face_recognition is None:
        return None

    try:
        # face_recognition returns (top, right, bottom, left)
        locations = face_recognition.face_locations(image_rgb, model="hog")
        if not locations:
            return None

        # Pick largest face
        locations = sorted(locations, key=lambda l: (l[2] - l[0]) * (l[1] - l[3]), reverse=True)
        top, right, bottom, left = locations[0]
        w = right - left
        h = bottom - top
        return (left, top, w, h)
    except Exception:
        return None


def extract_passport_photo(image_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Finds and crops the passport portrait photograph from the document.
    First uses deep face detection across the document; falls back to ICAO designated zone.
    """
    h, w = image_bgr.shape[:2]
    rgb_full = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    face_box = find_face_with_face_recognition(rgb_full)
    detection_method = "Deep dlib HOG Neural Detector"

    if face_box is not None:
        fx, fy, fw, fh = face_box
        # Expand face box to standard ICAO portrait proportions (~1.25 : 1.0 vertical framing)
        pad_x = int(fw * 0.40)
        pad_y_top = int(fh * 0.55)
        pad_y_bot = int(fh * 0.70)

        x1 = max(0, fx - pad_x)
        y1 = max(0, fy - pad_y_top)
        x2 = min(w, fx + fw + pad_x)
        y2 = min(h, fy + fh + pad_y_bot)

        portrait_bgr = image_bgr[y1:y2, x1:x2]
        bounding_box = {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
        face_found = True
    else:
        # Fallback to standard ICAO Doc 9303 portrait zone (left ~36% width, 12-82% height)
        x1 = int(w * 0.02)
        x2 = int(w * 0.38)
        y1 = int(h * 0.12)
        y2 = int(h * 0.82)

        portrait_bgr = image_bgr[y1:y2, x1:x2]
        bounding_box = {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
        detection_method = "ICAO TD3 Geometry Zone Fallback"
        face_found = False

    return {
        "portrait_bgr": portrait_bgr,
        "face_found": face_found,
        "bounding_box": bounding_box,
        "detection_method": detection_method,
        "preview_base64": image_to_base64(portrait_bgr),
    }


def analyze_photo_tampering_and_compliance(portrait_bgr: np.ndarray, full_doc_bgr: np.ndarray, photo_box: Dict[str, int]) -> Dict[str, Any]:
    """
    Performs forensic Photo Determination:
    1. Boundary splice / seam analysis (looks for artificial razor cut-lines or paste borders).
    2. Localized Error Level Analysis (ELA) on the portrait vs. ambient paper.
    3. Facial landmarks & head tilt (ICAO compliance).
    4. Color and lighting uniformity.
    """
    h, w = portrait_bgr.shape[:2]
    rgb_portrait = cv2.cvtColor(portrait_bgr, cv2.COLOR_BGR2RGB)
    flags: List[str] = []
    photo_risk_score = 0.0

    # 1. Check for face landmarks & head tilt using face_recognition
    landmarks_detected = False
    head_tilt_deg = 0.0
    eyes_horizontal = True

    if face_recognition is not None:
        try:
            landmarks_list = face_recognition.face_landmarks(rgb_portrait)
            if landmarks_list:
                landmarks_detected = True
                lm = landmarks_list[0]
                left_eye = lm.get("left_eye")
                right_eye = lm.get("right_eye")
                if left_eye and right_eye:
                    # Compute average center of each eye
                    l_center = np.mean(left_eye, axis=0)
                    r_center = np.mean(right_eye, axis=0)
                    dx = r_center[0] - l_center[0]
                    dy = r_center[1] - l_center[1]
                    head_tilt_deg = round(abs(math.degrees(math.atan2(dy, dx))), 1)
                    if head_tilt_deg > 22.0:
                        eyes_horizontal = False
                        photo_risk_score += 15.0
                        flags.append(f"Excessive head tilt ({head_tilt_deg}°) violates ICAO frontal portrait standard")
        except Exception:
            pass

    laplacian_var = 0.0
    splice_detected = False
    try:
        bx = photo_box["x"]
        by = photo_box["y"]
        bw = photo_box["width"]
        bh = photo_box["height"]
        doc_h, doc_w = full_doc_bgr.shape[:2]

        # Sample 6-pixel perimeter band around the photo
        pad = 6
        if by > pad and (by + bh + pad) < doc_h and bx > pad and (bx + bw + pad) < doc_w:
            outer_border = full_doc_bgr[by-pad:by+bh+pad, bx-pad:bx+bw+pad]
            gray_border = cv2.cvtColor(outer_border, cv2.COLOR_BGR2GRAY)
            # High frequency edge gradient along seam
            laplacian_var = float(cv2.Laplacian(gray_border, cv2.CV_64F).var())

            # Relative edge gradient ratio compared to internal portrait texture
            gray_inner = cv2.cvtColor(portrait_bgr, cv2.COLOR_BGR2GRAY)
            inner_var = float(cv2.Laplacian(gray_inner, cv2.CV_64F).var())
            gradient_ratio = laplacian_var / max(inner_var, 1.0)

            # An authentic passport photo naturally has sharp borders against security paper (1500-4000).
            # True physical photo splices or digital copy-pastes exhibit extreme seam variance (>7500 and ratio > 4.5).
            if laplacian_var > 7500 and gradient_ratio > 4.5:
                splice_detected = True
                photo_risk_score += 25.0
                flags.append(f"Sharp edge gradient discontinuity detected along photo perimeter (Laplacian: {int(laplacian_var)}, Ratio: {gradient_ratio:.1f})")
    except Exception:
        pass

    # 3. Photo-Specific Error Level Analysis (ELA)
    # Recompress portrait crop at JPEG 90 and measure difference
    buf = cv2.imencode(".jpg", portrait_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])[1]
    recomp = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    diff = cv2.absdiff(portrait_bgr, recomp)
    photo_ela_mean = float(np.mean(diff))
    photo_ela_std = float(np.std(diff))

    if photo_ela_std > 8.5 or photo_ela_mean > 7.0:
        photo_risk_score += 30.0
        flags.append(f"High compression noise disparity in portrait region (ELA Std: {photo_ela_std:.1f})")

    # 4. Color Discordance Check
    # Compare portrait background color to document paper background
    doc_sample = full_doc_bgr[int(full_doc_bgr.shape[0] * 0.2):int(full_doc_bgr.shape[0] * 0.4), int(full_doc_bgr.shape[1] * 0.5):int(full_doc_bgr.shape[1] * 0.7)]
    if doc_sample.size > 0:
        doc_mean_bgr = np.mean(doc_sample, axis=(0, 1))
        # Top corner of portrait (usually background behind traveler's head)
        corner_patch = portrait_bgr[:int(h * 0.15), :int(w * 0.25)]
        if corner_patch.size > 0:
            corner_mean_bgr = np.mean(corner_patch, axis=(0, 1))
            color_distance = np.linalg.norm(doc_mean_bgr - corner_mean_bgr)
            if color_distance > 65.0:
                photo_risk_score += 20.0
                flags.append(f"Chromatic discordance between photo backdrop and document substrate ({color_distance:.1f} color diff)")

    photo_risk_score = round(min(100.0, photo_risk_score), 1)

    if photo_risk_score >= 60.0:
        verdict = "HIGH TAMPER RISK: Potential Photo Splice Detected"
    elif photo_risk_score >= 30.0:
        verdict = "MODERATE RISK: Review Photo Perimeter & Lighting"
    else:
        verdict = "AUTHENTIC: Uniform Photo Integration & ICAO Alignment"

    return {
        "photo_risk_score": float(photo_risk_score),
        "splice_detected": bool(splice_detected),
        "edge_gradient_score": float(round(laplacian_var, 2)),
        "verdict": str(verdict),
        "flags": [str(f) for f in flags],
        "is_flagged": bool(photo_risk_score >= 30.0),
        "icao_compliance": {
            "face_detected": bool(landmarks_detected or (photo_box["width"] > 60)),
            "landmarks_detected": bool(landmarks_detected),
            "head_tilt_degrees": float(head_tilt_deg),
            "eyes_horizontal": bool(eyes_horizontal),
            "photo_ela_std": float(round(photo_ela_std, 2)),
        }
    }


def fallback_feature_similarity(f1: np.ndarray, f2: np.ndarray) -> float:
    """
    Fallback color and texture histogram similarity between two face crops
    when 128-d deep neural embeddings cannot be computed.
    """
    try:
        f1_res = cv2.resize(f1, (160, 200))
        f2_res = cv2.resize(f2, (160, 200))
        h1 = cv2.calcHist([cv2.cvtColor(f1_res, cv2.COLOR_BGR2HSV)], [0, 1], None, [30, 32], [0, 180, 0, 256])
        h2 = cv2.calcHist([cv2.cvtColor(f2_res, cv2.COLOR_BGR2HSV)], [0, 1], None, [30, 32], [0, 180, 0, 256])
        cv2.normalize(h1, h1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(h2, h2, 0, 1, cv2.NORM_MINMAX)
        corr = max(0.0, float(cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)))
        return round(corr * 100.0, 1)
    except Exception:
        return 50.0


def compare_faces(
    passport_image_bgr: np.ndarray,
    live_selfie_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Orchestrates Photo Determination and Biometric Facial Verification.
    1. Extracts and locates portrait photo on passport page.
    2. Runs forensic photo determination (splicing, ELA, ICAO compliance).
    3. If live selfie is supplied: extracts 128-d deep face encodings and calculates similarity %.
    """
    # 1. Locate and extract passport portrait
    extraction = extract_passport_photo(passport_image_bgr)
    portrait_bgr = extraction["portrait_bgr"]
    photo_box = extraction["bounding_box"]

    # 2. Comprehensive Forensic Photo Determination
    photo_forensics = analyze_photo_tampering_and_compliance(
        portrait_bgr=portrait_bgr,
        full_doc_bgr=passport_image_bgr,
        photo_box=photo_box
    )

    # Base response payload
    result = {
        "performed": False,
        "passport_face_detected": extraction["face_found"],
        "detection_method": extraction["detection_method"],
        "bounding_box": photo_box,
        "passport_face_preview_base64": extraction["preview_base64"],
        "live_face_preview_base64": None,
        "match_score": None,
        "is_match": None,
        "match_status": None,
        "match_verdict": None,
        "engine": "dlib 128-d Deep Face Encodings",
        "photo_determination": photo_forensics,
        "liveness_detected": False,
        "liveness_limitation_note": "Liveness/anti-spoofing is out of scope for this prototype.",
        "summary": photo_forensics["verdict"]
    }

    # If no live selfie was uploaded, return photo determination report directly
    if not live_selfie_bytes:
        result["message"] = "Passport portrait analyzed; live capture was not provided for 1:1 cross-verification."
        return result

    # 3. Decode live selfie image
    selfie_arr = np.frombuffer(live_selfie_bytes, np.uint8)
    selfie_bgr = cv2.imdecode(selfie_arr, cv2.IMREAD_COLOR)

    if selfie_bgr is None:
        result["error"] = "Failed to decode live selfie image"
        return result

    # Detect face in selfie
    rgb_selfie = cv2.cvtColor(selfie_bgr, cv2.COLOR_BGR2RGB)
    selfie_face_box = find_face_with_face_recognition(rgb_selfie)
    if selfie_face_box is not None:
        sx, sy, sw, sh = selfie_face_box
        pad_x = int(sw * 0.3)
        pad_y = int(sh * 0.4)
        sh_img, sw_img = selfie_bgr.shape[:2]
        x1 = max(0, sx - pad_x)
        y1 = max(0, sy - pad_y)
        x2 = min(sw_img, sx + sw + pad_x)
        y2 = min(sh_img, sy + sh + pad_y)
        selfie_crop = selfie_bgr[y1:y2, x1:x2]
        live_detected = True
    else:
        selfie_crop = selfie_bgr
        live_detected = False

    result["live_face_preview_base64"] = image_to_base64(selfie_crop)
    result["live_face_detected"] = live_detected
    result["performed"] = True

    # 4. Deep Face Encoding Biometric Comparison
    rgb_pass = cv2.cvtColor(portrait_bgr, cv2.COLOR_BGR2RGB)
    match_score = None
    engine_used = "dlib 128-d Face Encodings"

    if face_recognition is not None:
        try:
            pass_encs = face_recognition.face_encodings(rgb_pass)
            selfie_encs = face_recognition.face_encodings(rgb_selfie)

            if pass_encs and selfie_encs:
                distance = face_recognition.face_distance([pass_encs[0]], selfie_encs[0])[0]
                # In dlib: distance 0.0 is exact match, 0.4 is very confident, 0.6 is typical threshold
                sim = max(0.0, min(100.0, (1.0 - (distance)) * 100.0))
                match_score = round(sim, 1)
                engine_used = "dlib 128-d Deep Metric Euclidean Distance"
        except Exception:
            pass


    # Normalized structural fallback if encodings were unavailable
    if match_score is None:
        match_score = float(fallback_feature_similarity(portrait_bgr, selfie_crop))
        engine_used = "Color Chrominance Correlation Fallback"

    match_score = float(round(match_score, 1))

    # 1:1 Biometric Verification Threshold Calibration:
    # - Below 40.0: Mismatch (flag for secondary inspection)
    # - 40.0 to 55.0: Not Sure (manual review required)
    # - 55.0 and above: Pass (confirmed match)
    if match_score >= FACE_MATCH_PASS_MIN:
        match_status = "pass"
        match_verdict = "PASS"
        summary_verdict = "Pass (Match Confirmed)"
        is_match = True
    elif match_score >= FACE_MATCH_MISMATCH_MAX:
        match_status = "not_sure"
        match_verdict = "NOT SURE"
        summary_verdict = "Not Sure (Manual Review Required)"
        is_match = False
    else:
        match_status = "mismatch"
        match_verdict = "MISMATCH"
        summary_verdict = "Biometric Mismatch Flagged"
        is_match = False

    result["match_score"] = match_score
    result["is_match"] = is_match
    result["match_status"] = match_status
    result["match_verdict"] = match_verdict
    result["engine"] = str(engine_used)
    result["summary"] = f"Face match score: {match_score}% ({summary_verdict}) • {photo_forensics['verdict']}"

    return result
