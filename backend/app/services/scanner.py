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
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray, target_width: int = 1420, target_height: int = 1000) -> np.ndarray:
    """Applies perspective transformation to unwarp a quadrilateral region into a flat rectangle."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    if maxHeight > maxWidth:
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

    if warped.shape[0] > warped.shape[1]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

    return warped


def correct_glare_and_shadow(image: np.ndarray) -> np.ndarray:
    """Corrects uneven illumination, shadows, and glare using CLAHE on the L-channel."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    cl = clahe.apply(l_channel)
    merged_lab = cv2.merge((cl, a_channel, b_channel))
    return cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)


def sharpen_document(image: np.ndarray) -> np.ndarray:
    """Applies unsharp masking to enhance text edges and fine microprint details."""
    gaussian = cv2.GaussianBlur(image, (0, 0), sigmaX=1.5)
    sharpened = cv2.addWeighted(image, 1.35, gaussian, -0.35, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def image_to_base64(img_bgr: np.ndarray, format_ext: str = ".jpg") -> str:
    """Converts a BGR OpenCV image to a base64 encoded data URL."""
    success, buffer = cv2.imencode(format_ext, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not success:
        return ""
    b64_str = base64.b64encode(buffer).decode("utf-8")
    mime = "image/jpeg" if format_ext.lower() in [".jpg", ".jpeg"] else "image/png"
    return f"data:{mime};base64,{b64_str}"


def find_mrz_region(gray_image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Locates the Machine Readable Zone (MRZ) using morphological blackhat and gradient.
    MRZ lines exhibit strong high-frequency horizontal dark text contrast on light background.
    """
    h, w = gray_image.shape[:2]
    # Restrict to bottom 60% of image where MRZ resides
    roi_y = int(h * 0.4)
    roi_gray = gray_image[roi_y:, :]

    # Blackhat morphological filter to reveal dark text on light background
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
    blackhat = cv2.morphologyEx(roi_gray, cv2.MORPH_BLACKHAT, rect_kernel)

    # Compute Scharr gradient along X-axis
    grad_x = cv2.Sobel(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
    grad_x = np.absolute(grad_x)
    (min_val, max_val) = (np.min(grad_x), np.max(grad_x))
    if max_val > min_val:
        grad_x = (255 * ((grad_x - min_val) / (max_val - min_val))).astype("uint8")
    else:
        return None

    # Blur and close gaps horizontally
    grad_x = cv2.GaussianBlur(grad_x, (3, 3), 0)
    grad_x = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 5)))
    _, thresh = cv2.threshold(grad_x, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Further horizontal closing
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (33, 5)))

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        (x, y, cw, ch) = cv2.boundingRect(c)
        ar = cw / float(ch) if ch > 0 else 0
        # MRZ band is wide and relatively short (aspect ratio typically >= 4.0, width >= 45% of page)
        if ar >= 3.5 and cw >= (w * 0.45):
            candidates.append((x, roi_y + y, cw, ch))

    if candidates:
        # Pick the lowest MRZ candidate (closest to document bottom)
        candidates = sorted(candidates, key=lambda b: b[1], reverse=True)
        return candidates[0]

    return None


def crop_from_mrz_anchor(original_bgr: np.ndarray, mrz_box: Tuple[int, int, int, int]) -> np.ndarray:
    """
    Given the MRZ bounding box, reconstructs the full ICAO TD3 passport bio-data page.
    In TD3 passports, the bio-page height is approximately 1.42:1 aspect ratio relative to width,
    and the MRZ occupies the bottom ~22% of the page height.
    """
    img_h, img_w = original_bgr.shape[:2]
    mx, my, mw, mh = mrz_box

    # Estimated bio-page width and height based on MRZ span
    doc_w = int(mw * 1.08)
    doc_h = int(doc_w / PASSPORT_ASPECT_RATIO)

    # Center horizontally around MRZ
    center_x = mx + (mw // 2)
    x1 = max(0, center_x - (doc_w // 2))
    x2 = min(img_w, x1 + doc_w)

    # MRZ bottom is approximately the document bottom
    bottom_y = min(img_h, my + mh + int(mh * 0.35))
    top_y = max(0, bottom_y - doc_h)

    crop = original_bgr[top_y:bottom_y, x1:x2]
    return cv2.resize(crop, (1420, 1000), interpolation=cv2.INTER_CUBIC)


def scan_passport(
    image_bytes: bytes,
    force_fallback: bool = False,
    crop_mode: str = "auto"
) -> Dict[str, Any]:
    """
    Multi-strategy Auto Passport Scanner:
    1. Preset manual modes ('bottom_half', 'top_half', 'full').
    2. Contour detection with minAreaRect to accommodate rounded corners.
    3. Open booklet detection (splits 2-page passport into bio-data page).
    4. MRZ-guided anchor cropping (ground-truth fallback).
    """
    np_arr = np.frombuffer(image_bytes, np.uint8)
    original_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if original_bgr is None:
        raise ScannerError("Unable to decode input image file. Ensure it is a valid JPEG or PNG.")

    orig_h, orig_w = original_bgr.shape[:2]
    preview_orig_b64 = image_to_base64(original_bgr)

    # Handle preset manual crop modes
    if crop_mode == "bottom_half":
        # Standard open passport booklet (bio-page is bottom half)
        split_y = int(orig_h * 0.46)
        crop = original_bgr[split_y:, :]
        warped = cv2.resize(crop, (1420, 1000), interpolation=cv2.INTER_CUBIC)
        glare_corrected = correct_glare_and_shadow(warped)
        final_scan = sharpen_document(glare_corrected)
        return {
            "cropped_bgr": final_scan,
            "preview_cropped_base64": image_to_base64(final_scan),
            "preview_original_base64": preview_orig_b64,
            "contour_detected": True,
            "aspect_ratio": 1.42,
            "crop_method": "Preset: Bottom Half Bio-Page",
            "dimensions": {"width": 1420, "height": 1000},
        }

    if crop_mode == "top_half":
        split_y = int(orig_h * 0.54)
        crop = original_bgr[:split_y, :]
        warped = cv2.resize(crop, (1420, 1000), interpolation=cv2.INTER_CUBIC)
        glare_corrected = correct_glare_and_shadow(warped)
        final_scan = sharpen_document(glare_corrected)
        return {
            "cropped_bgr": final_scan,
            "preview_cropped_base64": image_to_base64(final_scan),
            "preview_original_base64": preview_orig_b64,
            "contour_detected": True,
            "aspect_ratio": 1.42,
            "crop_method": "Preset: Top Half Bio-Page",
            "dimensions": {"width": 1420, "height": 1000},
        }

    if crop_mode == "full":
        warped = cv2.resize(original_bgr, (1420, 1000), interpolation=cv2.INTER_CUBIC)
        glare_corrected = correct_glare_and_shadow(warped)
        final_scan = sharpen_document(glare_corrected)
        return {
            "cropped_bgr": final_scan,
            "preview_cropped_base64": image_to_base64(final_scan),
            "preview_original_base64": preview_orig_b64,
            "contour_detected": False,
            "aspect_ratio": round(orig_w / orig_h, 3),
            "crop_method": "Manual: Full Frame",
            "dimensions": {"width": 1420, "height": 1000},
        }

    # ========================================================
    # AUTO DETECTION PIPELINE (Multi-strategy)
    # ========================================================
    scale_ratio = 800.0 / max(orig_h, orig_w)
    if scale_ratio < 1.0:
        small_w = int(orig_w * scale_ratio)
        small_h = int(orig_h * scale_ratio)
        resized = cv2.resize(original_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA)
    else:
        scale_ratio = 1.0
        resized = original_bgr.copy()

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Strategy 1: Multi-threshold Canny + minAreaRect to accommodate rounded corners
    warped = None
    crop_method = "Contour Edge Detection"
    contour_detected = False
    best_aspect_ratio = 0.0

    # Try both adaptive threshold and Otsu edge detection
    for thresh_method in ["otsu", "adaptive", "sobel"]:
        if warped is not None:
            break

        if thresh_method == "otsu":
            high_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            edges = cv2.Canny(blurred, 0.4 * high_thresh, high_thresh)
        elif thresh_method == "adaptive":
            ad_thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            edges = cv2.Canny(ad_thresh, 50, 150)
        else:
            grad = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            _, edges = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        image_area = resized.shape[0] * resized.shape[1]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < (image_area * 0.12):
                continue

            # Compute minimum area rectangle (robust against rounded corners)
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (rw, rh), angle = rect
            if rw == 0 or rh == 0:
                continue

            ratio = max(rw, rh) / min(rw, rh)

            # Case A: Matches single bio-data page (~1.42:1)
            if (PASSPORT_ASPECT_RATIO - ASPECT_RATIO_TOLERANCE) <= ratio <= (PASSPORT_ASPECT_RATIO + ASPECT_RATIO_TOLERANCE):
                box = cv2.boxPoints(rect)
                pts_orig = (box / scale_ratio).astype("float32")
                warped = four_point_transform(original_bgr, pts_orig, target_width=1420, target_height=1000)
                contour_detected = True
                best_aspect_ratio = ratio
                crop_method = "Contour Box (TD3 Single Page)"
                break

            # Case B: Matches full open passport booklet (~0.7 or ~1.4 ratio for 2 pages)
            # In an open passport (top page + bottom bio-page), the booklet area is large (>= 30% frame)
            if area >= (image_area * 0.28):
                # Isolate the bottom half where the bio-data page is located
                box = cv2.boxPoints(rect)
                ordered = order_points(box)
                # If vertical open booklet (height > width)
                if (ordered[3][1] - ordered[0][1]) > (ordered[1][0] - ordered[0][0]) * 1.1:
                    # Cut bottom 52% of the booklet
                    mid_left = ordered[0] + (ordered[3] - ordered[0]) * 0.48
                    mid_right = ordered[1] + (ordered[2] - ordered[1]) * 0.48
                    bio_pts = np.array([mid_left, mid_right, ordered[2], ordered[3]], dtype="float32")
                    pts_orig = (bio_pts / scale_ratio).astype("float32")
                    warped = four_point_transform(original_bgr, pts_orig, target_width=1420, target_height=1000)
                    contour_detected = True
                    best_aspect_ratio = 1.42
                    crop_method = "Open Passport Booklet (Auto-Isolated Bio-Page)"
                    break

    # Strategy 2: MRZ-Guided Anchor Detection (If contours were too messy)
    if warped is None:
        mrz_box = find_mrz_region(cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY))
        if mrz_box is not None:
            try:
                warped = crop_from_mrz_anchor(original_bgr, mrz_box)
                contour_detected = True
                best_aspect_ratio = 1.42
                crop_method = "MRZ Anchor Landmark Localization"
            except Exception:
                warped = None

    # Strategy 3: Check if input image is already roughly passport aspect ratio
    if warped is None:
        image_ratio = max(orig_w, orig_h) / min(orig_w, orig_h)
        if (PASSPORT_ASPECT_RATIO - ASPECT_RATIO_TOLERANCE) <= image_ratio <= (PASSPORT_ASPECT_RATIO + ASPECT_RATIO_TOLERANCE):
            warped = cv2.resize(original_bgr, (1420, 1000), interpolation=cv2.INTER_CUBIC)
            if warped.shape[0] > warped.shape[1]:
                warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
            contour_detected = True
            best_aspect_ratio = image_ratio
            crop_method = "Direct Aspect Ratio Normalization"

    # Strategy 4: Fallback mode or Open Passport default split
    if warped is None:
        if force_fallback:
            # If the user took an open passport booklet photo (height >= width), cut bottom 52%
            if orig_h >= orig_w * 0.9:
                split_y = int(orig_h * 0.47)
                crop = original_bgr[split_y:, :]
                warped = cv2.resize(crop, (1420, 1000), interpolation=cv2.INTER_CUBIC)
                crop_method = "Fallback: Open Booklet Bottom Split"
            else:
                warped = cv2.resize(original_bgr, (1420, 1000), interpolation=cv2.INTER_CUBIC)
                crop_method = "Fallback: Full Frame"
            contour_detected = False
            best_aspect_ratio = round(orig_w / orig_h, 3)
        else:
            raise ScannerError(
                "Could not reliably detect passport bio-data page borders. "
                "Ensure the photo is clear, or choose 'Bottom Half (Open Booklet)' / 'Force Full Crop' in Document Intake options."
            )

    # Post-processing enhancements
    glare_corrected = correct_glare_and_shadow(warped)
    final_scan = sharpen_document(glare_corrected)

    return {
        "cropped_bgr": final_scan,
        "preview_cropped_base64": image_to_base64(final_scan),
        "preview_original_base64": preview_orig_b64,
        "contour_detected": contour_detected,
        "aspect_ratio": round(best_aspect_ratio, 3),
        "crop_method": crop_method,
        "dimensions": {"width": final_scan.shape[1], "height": final_scan.shape[0]},
    }
