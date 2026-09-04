import base64
import os
from typing import Dict, Any, Optional, Tuple

import cv2
import numpy as np

try:
    import face_recognition
except ImportError:
    face_recognition = None


def get_haar_cascade() -> Optional[Any]:
    """Loads OpenCV's frontal face Haar Cascade classifier if available."""
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade_path):
            try:
                return cv2.CascadeClassifier(cascade_path)
            except Exception:
                return None
    return None


def crop_passport_photo_region(image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
    """
    Extracts the passport portrait photograph.
    ICAO Doc 9303 standard positions the holder's portrait in the left ~36% of the TD3 page.
    """
    h, w = image_bgr.shape[:2]

    # Region of Interest for passport portrait photo (left ~36% width, upper 80% height)
    photo_roi_x1 = int(w * 0.02)
    photo_roi_x2 = int(w * 0.38)
    photo_roi_y1 = int(h * 0.12)
    photo_roi_y2 = int(h * 0.82)

    roi = image_bgr[photo_roi_y1:photo_roi_y2, photo_roi_x1:photo_roi_x2]
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Detect face inside photo ROI if cascade is available
    cascade = get_haar_cascade()
    if cascade is not None:
        try:
            faces = cascade.detectMultiScale(gray_roi, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
                fx, fy, fw, fh = faces[0]
                pad_x = int(fw * 0.25)
                pad_y = int(fh * 0.35)
                x1 = max(0, fx - pad_x)
                y1 = max(0, fy - pad_y)
                x2 = min(roi.shape[1], fx + fw + pad_x)
                y2 = min(roi.shape[0], fy + fh + pad_y)
                cropped_face = roi[y1:y2, x1:x2]
                global_coords = (photo_roi_x1 + x1, photo_roi_y1 + y1, x2 - x1, y2 - y1)
                return cropped_face, global_coords
        except Exception:
            pass

    # Fallback: scan whole image if cascade available and ROI didn't yield a face
    if cascade is not None:
        try:
            gray_full = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            full_faces = cascade.detectMultiScale(gray_full, scaleFactor=1.15, minNeighbors=4, minSize=(80, 80))
            if len(full_faces) > 0:
                full_faces = sorted(full_faces, key=lambda r: r[2] * r[3], reverse=True)
                fx, fy, fw, fh = full_faces[0]
                pad_x = int(fw * 0.2)
                pad_y = int(fh * 0.3)
                x1 = max(0, fx - pad_x)
                y1 = max(0, fy - pad_y)
                x2 = min(w, fx + fw + pad_x)
                y2 = min(h, fy + fh + pad_y)
                return image_bgr[y1:y2, x1:x2], (x1, y1, x2 - x1, y2 - y1)
        except Exception:
            pass

    # Default fallback: return designated ICAO portrait region directly
    return roi, (photo_roi_x1, photo_roi_y1, photo_roi_x2 - photo_roi_x1, photo_roi_y2 - photo_roi_y1)


def detect_and_crop_selfie_face(image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], bool]:
    """Detects and crops face from a live webcam capture."""
    cascade = get_haar_cascade()
    if cascade is None:
        # Cascade not present; center crop selfie face region
        h, w = image_bgr.shape[:2]
        pad_y = int(h * 0.1)
        pad_x = int(w * 0.15)
        return image_bgr[pad_y:h-pad_y, pad_x:w-pad_x], True

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    try:
        faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(100, 100))
        if len(faces) == 0:
            return image_bgr, False

        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
        fx, fy, fw, fh = faces[0]

        pad_x = int(fw * 0.3)
        pad_y = int(fh * 0.4)
        h, w = image_bgr.shape[:2]
        x1 = max(0, fx - pad_x)
        y1 = max(0, fy - pad_y)
        x2 = min(w, fx + fw + pad_x)
        y2 = min(h, fy + fh + pad_y)

        return image_bgr[y1:y2, x1:x2], True
    except Exception:
        return image_bgr, True


def fallback_feature_similarity(face1_bgr: np.ndarray, face2_bgr: np.ndarray) -> float:
    """
    Color histogram and structural similarity fallback when dlib / face_recognition is not installed.
    Computes normalized HSV histogram correlation and edge structure similarity.
    """
    try:
        # Resize both to identical resolution
        f1 = cv2.resize(face1_bgr, (160, 200))
        f2 = cv2.resize(face2_bgr, (160, 200))

        # HSV Color histograms
        hsv1 = cv2.cvtColor(f1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(f2, cv2.COLOR_BGR2HSV)

        hist1 = cv2.calcHist([hsv1], [0, 1], None, [30, 32], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [30, 32], [0, 180, 0, 256])

        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)

        hist_corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

        # Grayscale normalized correlation
        g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(g1, g2, cv2.TM_CCOEFF_NORMED)
        template_corr = float(res[0][0])

        combined = max(0.0, min(1.0, (hist_corr * 0.5) + (template_corr * 0.5)))
        return round(combined * 100.0, 1)
    except Exception:
        return 50.0


def compare_faces(
    passport_image_bgr: np.ndarray,
    live_selfie_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Extracts face from passport bio-data page and matches against live selfie capture.
    """
    # 1. Crop passport face
    passport_face, coords = crop_passport_photo_region(passport_image_bgr)
    passport_face_b64 = ""
    if passport_face is not None:
        _, buf = cv2.imencode(".jpg", passport_face, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        passport_face_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

    # If no live selfie provided, return passport crop only
    if not live_selfie_bytes:
        return {
            "performed": False,
            "passport_face_detected": passport_face is not None,
            "live_face_detected": False,
            "match_score": None,
            "is_match": None,
            "passport_face_preview_base64": passport_face_b64,
            "live_face_preview_base64": None,
            "liveness_detected": False,
            "liveness_limitation_note": "Liveness/anti-spoofing is out of scope for this prototype. Live selfie was not provided.",
            "message": "Passport photo extracted; live capture not provided for verification."
        }

    # 2. Decode live selfie
    selfie_arr = np.frombuffer(live_selfie_bytes, np.uint8)
    selfie_bgr = cv2.imdecode(selfie_arr, cv2.IMREAD_COLOR)

    if selfie_bgr is None:
        return {
            "performed": False,
            "error": "Failed to decode live selfie image",
            "match_score": None,
            "passport_face_preview_base64": passport_face_b64,
            "live_face_preview_base64": None,
        }

    selfie_face, live_detected = detect_and_crop_selfie_face(selfie_bgr)
    _, s_buf = cv2.imencode(".jpg", selfie_face, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    live_face_b64 = f"data:image/jpeg;base64,{base64.b64encode(s_buf).decode('utf-8')}"

    # 3. Match calculation
    match_score = None
    engine_used = "OpenCV Feature Heuristic Fallback"

    # Try face_recognition (dlib) if installed
    if face_recognition is not None and passport_face is not None:
        try:
            rgb_pass = cv2.cvtColor(passport_face, cv2.COLOR_BGR2RGB)
            rgb_live = cv2.cvtColor(selfie_face, cv2.COLOR_BGR2RGB)

            enc_pass = face_recognition.face_encodings(rgb_pass)
            enc_live = face_recognition.face_encodings(rgb_live)

            if len(enc_pass) > 0 and len(enc_live) > 0:
                engine_used = "dlib 128-d Face Encodings"
                dist = face_recognition.face_distance([enc_pass[0]], enc_live[0])[0]
                # In dlib, distance < 0.6 is typical match
                # Convert distance into similarity percentage
                sim = max(0.0, min(100.0, (1.0 - (dist / 0.65)) * 100.0))
                match_score = round(sim, 1)
        except Exception:
            pass

    if match_score is None and passport_face is not None and selfie_face is not None:
        match_score = fallback_feature_similarity(passport_face, selfie_face)

    is_match = match_score >= 60.0 if match_score is not None else False

    return {
        "performed": True,
        "passport_face_detected": passport_face is not None,
        "live_face_detected": live_detected,
        "match_score": match_score,
        "is_match": is_match,
        "engine": engine_used,
        "passport_face_preview_base64": passport_face_b64,
        "live_face_preview_base64": live_face_b64,
        "liveness_detected": False,
        "liveness_limitation_note": "Liveness/anti-spoofing is out of scope for this prototype. Face verification measures visual similarity only.",
        "summary": f"Face match score: {match_score}% ({'Match' if is_match else 'Low similarity'})"
    }
