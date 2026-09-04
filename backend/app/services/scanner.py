import base64
import io
import math
from typing import Tuple, Optional, Dict, Any, List

import cv2
import numpy as np
from PIL import Image

from ..config import PASSPORT_ASPECT_RATIO, ASPECT_RATIO_TOLERANCE


class ScannerError(Exception):
    """Raised when document boundary detection fails to locate a valid passport."""
    pass


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders 4 coordinates clockwise starting from top-left:
    [top-left, top-right, bottom-right, bottom-left]
    """
    rect = np.zeros((4, 2), dtype="float32")

    # sum: top-left has smallest sum, bottom-right has largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # diff: top-right has smallest diff (x - y), bottom-left has largest diff
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray, target_width: int = 1420, target_height: int = 1000) -> np.ndarray:
    """
    Applies perspective transformation to unwarp a quadrilateral region into a flat rectangle.
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # Compute widths and heights of the candidate
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # Standardize to landscape TD3 orientation (width > height)
    if maxHeight > maxWidth:
        # Document is rotated vertically; adjust target orientation
        out_w, out_h = target_height, target_width
    else:
        out_w, out_h = target_width, target_height

    dst = np.array([
        [0, 0],
        [out_w - 1, 0],
        [out_w - 1, out_h - 1],
        [0, out_h - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (out_w, out_h), flags=cv2.INTER_CUBIC)

    # If warped height > width, rotate 90 degrees clockwise to keep landscape
    if warped.shape[0] > warped.shape[1]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

    return warped


def correct_glare_and_shadow(image: np.ndarray) -> np.ndarray:
    """
    Corrects uneven illumination, shadows, and glare using CLAHE on the L-channel (LAB color space).
    """
    # Convert BGR to LAB
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(l_channel)

    # Merge channels back
    merged_lab = cv2.merge((cl, a_channel, b_channel))
    corrected_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
    return corrected_bgr


def sharpen_document(image: np.ndarray) -> np.ndarray:
    """
    Applies unsharp masking to enhance text edges and fine microprint details.
    """
    gaussian = cv2.GaussianBlur(image, (0, 0), sigmaX=1.5)
    sharpened = cv2.addWeighted(image, 1.4, gaussian, -0.4, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def image_to_base64(img_bgr: np.ndarray, format_ext: str = ".jpg") -> str:
    """Converts a BGR OpenCV image to a base64 encoded data URL."""
    success, buffer = cv2.imencode(format_ext, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not success:
        return ""
    b64_str = base64.b64encode(buffer).decode("utf-8")
    mime = "image/jpeg" if format_ext.lower() in [".jpg", ".jpeg"] else "image/png"
    return f"data:{mime};base64,{b64_str}"


def scan_passport(
    image_bytes: bytes,
    force_fallback: bool = False
) -> Dict[str, Any]:
    """
    Auto-detects passport bio-data page contour, crops, deskews, and enhances it.

    Parameters:
        image_bytes: Raw bytes of uploaded image.
        force_fallback: If True, falls back to full image crop when no 4-point contour is found.

    Returns:
        Dictionary containing:
        - cropped_bgr: np.ndarray (OpenCV BGR image)
        - preview_cropped_base64: str (data URL for UI preview)
        - preview_original_base64: str (data URL of original)
        - contour_detected: bool
        - aspect_ratio: float
        - metadata: dict
    """
    # Decode bytes to OpenCV image
    np_arr = np.frombuffer(image_bytes, np.uint8)
    original_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if original_bgr is None:
        raise ScannerError("Unable to decode input image file. Ensure it is a valid JPEG or PNG.")

    orig_h, orig_w = original_bgr.shape[:2]
    preview_orig_b64 = image_to_base64(original_bgr)

    # Resize for fast, robust contour detection while preserving original
    scale_ratio = 800.0 / max(orig_h, orig_w)
    if scale_ratio < 1.0:
        small_w = int(orig_w * scale_ratio)
        small_h = int(orig_h * scale_ratio)
        resized = cv2.resize(original_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA)
    else:
        scale_ratio = 1.0
        resized = original_bgr.copy()

    # Preprocessing pipeline
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny edge detection with Otsu threshold estimation
    high_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    low_thresh = 0.5 * high_thresh
    edges = cv2.Canny(blurred, low_thresh, high_thresh)

    # Dilate edges to close gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    passport_contour = None
    best_aspect_ratio = 0.0
    detected_contour_points: Optional[List[List[int]]] = None

    image_area = resized.shape[0] * resized.shape[1]
    min_doc_area = image_area * 0.15  # At least 15% of frame

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_doc_area:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        # Check for 4-point polygon
        if len(approx) == 4:
            pts = approx.reshape(4, 2)
            # Calculate aspect ratio
            rect = order_points(pts)
            w_top = np.linalg.norm(rect[1] - rect[0])
            w_bot = np.linalg.norm(rect[2] - rect[3])
            h_left = np.linalg.norm(rect[3] - rect[0])
            h_right = np.linalg.norm(rect[2] - rect[1])
            avg_w = (w_top + w_bot) / 2.0
            avg_h = (h_left + h_right) / 2.0

            if avg_h == 0 or avg_w == 0:
                continue

            # Normalized aspect ratio (always >= 1.0)
            ratio = max(avg_w, avg_h) / min(avg_w, avg_h)

            # ICAO TD3 passport bio-page is ~1.4205:1
            lower_bound = PASSPORT_ASPECT_RATIO - ASPECT_RATIO_TOLERANCE
            upper_bound = PASSPORT_ASPECT_RATIO + ASPECT_RATIO_TOLERANCE

            if lower_bound <= ratio <= upper_bound:
                passport_contour = approx
                best_aspect_ratio = ratio
                detected_contour_points = (pts / scale_ratio).astype(int).tolist()
                break

    if passport_contour is not None:
        # Scale contour back to original image resolution
        pts_orig = (passport_contour.reshape(4, 2) / scale_ratio).astype("float32")
        warped = four_point_transform(original_bgr, pts_orig, target_width=1420, target_height=1000)
        contour_detected = True
    else:
        if not force_fallback:
            # Check if image itself already has approximately the passport aspect ratio (e.g. cropped scan)
            image_ratio = max(orig_w, orig_h) / min(orig_w, orig_h)
            if (PASSPORT_ASPECT_RATIO - ASPECT_RATIO_TOLERANCE) <= image_ratio <= (PASSPORT_ASPECT_RATIO + ASPECT_RATIO_TOLERANCE):
                warped = original_bgr.copy()
                if warped.shape[0] > warped.shape[1]:
                    warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
                contour_detected = True
                best_aspect_ratio = image_ratio
            else:
                raise ScannerError(
                    "No valid passport-shaped contour (~1.42:1 aspect ratio) detected. "
                    "Please provide a clearer photo with the passport bio-data page fully visible against a contrasting background, "
                    "or enable manual crop / force scan."
                )
        else:
            # Fallback mode: use entire image
            warped = original_bgr.copy()
            if warped.shape[0] > warped.shape[1]:
                warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
            contour_detected = False
            best_aspect_ratio = max(orig_w, orig_h) / min(orig_w, orig_h)

    # Post-warp enhancement: glare / shadow correction via CLAHE
    glare_corrected = correct_glare_and_shadow(warped)

    # Sharpen to emphasize fine font edges
    final_scan = sharpen_document(glare_corrected)

    preview_cropped_b64 = image_to_base64(final_scan)

    return {
        "cropped_bgr": final_scan,
        "preview_cropped_base64": preview_cropped_b64,
        "preview_original_base64": preview_orig_b64,
        "contour_detected": contour_detected,
        "aspect_ratio": round(best_aspect_ratio, 3),
        "dimensions": {"width": final_scan.shape[1], "height": final_scan.shape[0]},
        "contour_points": detected_contour_points,
    }
