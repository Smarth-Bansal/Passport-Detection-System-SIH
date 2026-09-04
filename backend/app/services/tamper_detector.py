import base64
import io
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

try:
    import exifread
except ImportError:
    exifread = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from ..config import (
    MODEL_PATH,
    WEIGHT_CNN_MODEL,
    WEIGHT_ELA_DIFF,
    WEIGHT_EXIF_FORENSICS,
    WEIGHT_MRZ_CHECKSUM,
)

# Global ONNX session cache
_onnx_session: Optional[Any] = None


def get_onnx_session() -> Optional[Any]:
    """Loads and caches the ONNX runtime inference session on CPU."""
    global _onnx_session
    if _onnx_session is not None:
        return _onnx_session

    if ort is None:
        return None

    if os.path.exists(MODEL_PATH):
        try:
            # Explicitly force CPU provider for lightweight, portable deployment
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            _onnx_session = ort.InferenceSession(
                MODEL_PATH,
                sess_options=opts,
                providers=["CPUExecutionProvider"]
            )
        except Exception:
            _onnx_session = None

    return _onnx_session


def run_onnx_tamper_inference(image_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Preprocesses the document image and feeds it to the lightweight ONNX CNN model.
    Expected input shape: [1, 3, 224, 224] normalized with ImageNet stats.
    """
    session = get_onnx_session()
    if session is None:
        # If model file is not yet downloaded or runtime missing, return baseline heuristic
        return {
            "available": False,
            "tamper_probability": 0.08,
            "tamper_score": 8.0,
            "status": "ONNX model not loaded, using baseline signal",
        }

    try:
        # Resize to 224x224
        resized = cv2.resize(image_bgr, (224, 224), interpolation=cv2.INTER_AREA)
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (rgb - mean) / std

        # Convert HWC to NCHW
        tensor = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)

        # Run inference
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})

        # Softmax or sigmoid probability
        raw_output = outputs[0]
        if raw_output.shape[-1] == 2:
            # 2 classes: [authentic, tampered]
            exp_vals = np.exp(raw_output - np.max(raw_output))
            probs = exp_vals / np.sum(exp_vals, axis=-1, keepdims=True)
            tamper_prob = float(probs[0][1])
        else:
            # Single logit with sigmoid
            val = float(raw_output.flatten()[0])
            tamper_prob = float(1.0 / (1.0 + np.exp(-val)))

        return {
            "available": True,
            "tamper_probability": round(tamper_prob, 4),
            "tamper_score": round(tamper_prob * 100.0, 1),
            "status": "Inference completed successfully",
        }
    except Exception as e:
        return {
            "available": False,
            "tamper_probability": 0.15,
            "tamper_score": 15.0,
            "status": f"Inference error: {str(e)}",
        }


def compute_error_level_analysis(
    image_bgr: np.ndarray,
    quality: int = 90,
    scale_multiplier: int = 12
) -> Dict[str, Any]:
    """
    Error Level Analysis (ELA):
    Re-saves the image at a known JPEG compression quality (default 90) and measures
    the pixel-level reconstruction error. Spliced/pasted photo or text edits produce
    distinct localized compression differences.
    """
    # Convert BGR to RGB PIL image
    rgb_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil_orig = Image.fromarray(rgb_img)

    # Save to memory buffer at specific quality
    buf = io.BytesIO()
    pil_orig.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    pil_recompressed = Image.open(buf)

    # Compute difference
    diff = ImageChops.difference(pil_orig, pil_recompressed)

    # Convert diff to numpy array
    diff_arr = np.array(diff, dtype=np.float32)

    # Amplify difference
    diff_amplified = np.clip(diff_arr * scale_multiplier, 0, 255).astype(np.uint8)

    # Calculate statistics
    mean_diff = float(np.mean(diff_arr))
    max_diff = float(np.max(diff_arr))
    std_diff = float(np.std(diff_arr))

    # Anomaly metric: high localized variance or extreme peak indicates tampering
    # Normal camera capture has mean diff ~2-5 and std ~2-4. Edits produce std > 8 and peak clusters
    anomaly_score = min(100.0, max(0.0, (std_diff * 4.5) + (mean_diff * 3.0)))

    # Generate a visual heatmap for the frontend using COLORMAP_JET
    diff_gray = cv2.cvtColor(diff_amplified, cv2.COLOR_RGB2GRAY)
    heatmap = cv2.applyColorMap(diff_gray, cv2.COLORMAP_JET)

    # Blend original with heatmap for context
    blend = cv2.addWeighted(image_bgr, 0.4, heatmap, 0.6, 0)

    # Encode heatmap to base64
    success, buffer = cv2.imencode(".jpg", blend, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    heatmap_b64 = ""
    if success:
        b64_str = base64.b64encode(buffer).decode("utf-8")
        heatmap_b64 = f"data:image/jpeg;base64,{b64_str}"

    flagged = anomaly_score > 45.0

    return {
        "score": round(anomaly_score, 1),
        "mean_diff": round(mean_diff, 2),
        "max_diff": round(max_diff, 2),
        "std_diff": round(std_diff, 2),
        "flagged": flagged,
        "heatmap_base64": heatmap_b64,
        "detail": "High compression variation detected; possible spliced image or modified text block"
        if flagged else "Uniform compression levels consistent with authentic capture"
    }


def analyze_exif_forensics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Parses EXIF headers and metadata to detect editing signatures, stripped tags,
    or timestamp inconsistencies.
    """
    suspicious_software_keywords = [
        "photoshop", "gimp", "canva", "paint.net", "snapseed", "lightroom",
        "pixlr", "affinity", "pixelmator", "coreldraw", "seashore"
    ]

    software_tag = None
    has_exif = False
    timestamp_mismatch = False
    tags_found: Dict[str, str] = {}
    flags: List[str] = []

    try:
        # Check with Pillow first
        pil_img = Image.open(io.BytesIO(image_bytes))
        info = getattr(pil_img, "_getexif", lambda: None)()
        if info:
            has_exif = True
            for tag_id, value in info.items():
                val_str = str(value)
                if "software" in str(tag_id).lower():
                    software_tag = val_str

        # Check with exifread if available
        if exifread is not None:
            buf = io.BytesIO(image_bytes)
            exif_tags = exifread.process_file(buf, details=False)
            if exif_tags:
                has_exif = True
                for tag, val in exif_tags.items():
                    tags_found[tag] = str(val)
                    if "software" in tag.lower():
                        software_tag = str(val)

                    if "DateTimeOriginal" in tag and "DateTimeDigitized" in exif_tags:
                        orig = str(val)
                        digi = str(exif_tags["DateTimeDigitized"])
                        if orig and digi and orig != digi:
                            timestamp_mismatch = True

    except Exception:
        pass

    # Score determination
    score = 0.0

    if software_tag:
        sw_lower = software_tag.lower()
        matched_sw = [kw for kw in suspicious_software_keywords if kw in sw_lower]
        if matched_sw:
            score += 75.0
            flags.append(f"Image edited with known graphic manipulation software: '{software_tag}'")
        else:
            score += 20.0
            flags.append(f"Software metadata present: '{software_tag}'")
    else:
        # Missing EXIF in phone images is common when uploaded via web, but still a mild signal
        if not has_exif:
            score += 15.0
            flags.append("EXIF metadata is stripped or absent (common in web re-saves or exported edits)")

    if timestamp_mismatch:
        score += 25.0
        flags.append("Creation timestamp disagrees with digitization timestamp")

    score = min(100.0, score)

    return {
        "score": round(score, 1),
        "has_exif": has_exif,
        "software_tag": software_tag,
        "timestamp_mismatch": timestamp_mismatch,
        "flagged": score >= 50.0,
        "flags": flags,
        "summary": flags[0] if flags else "No editing software signatures found in metadata"
    }


def detect_tampering(
    image_bgr: np.ndarray,
    raw_image_bytes: bytes,
    mrz_checksum_valid: bool = True
) -> Dict[str, Any]:
    """
    Ensembles multiple independent forensic signals:
    1. ONNX CNN Forgery Classifier
    2. Error Level Analysis (ELA) Re-compression Anomaly
    3. EXIF Metadata Forensics
    4. MRZ Checksum Integrity Signal
    Returns an aggregated 0-100 Tamper Risk Score with an itemized breakdown.
    """
    # 1. ONNX Inference
    onnx_res = run_onnx_tamper_inference(image_bgr)
    cnn_score = onnx_res.get("tamper_score", 10.0)

    # 2. ELA
    ela_res = compute_error_level_analysis(image_bgr)
    ela_score = ela_res.get("score", 0.0)

    # 3. EXIF Forensics
    exif_res = analyze_exif_forensics(raw_image_bytes)
    exif_score = exif_res.get("score", 0.0)

    # 4. MRZ Checksum Signal
    # If checksum failed, it is mathematically verified tampering/mismatch
    mrz_tamper_score = 0.0 if mrz_checksum_valid else 95.0

    # Ensemble calculation
    total_score = (
        (cnn_score * WEIGHT_CNN_MODEL) +
        (ela_score * WEIGHT_ELA_DIFF) +
        (exif_score * WEIGHT_EXIF_FORENSICS) +
        (mrz_tamper_score * WEIGHT_MRZ_CHECKSUM)
    )
    final_score = round(min(100.0, max(0.0, total_score)), 1)

    # Assemble triggered signals list
    triggered_signals = []
    if cnn_score >= 60.0:
        triggered_signals.append(f"CNN Model flagged forgery pattern ({cnn_score}% probability)")
    if ela_res.get("flagged"):
        triggered_signals.append(f"ELA detected localized compression disparity ({ela_score} anomaly score)")
    if exif_res.get("flagged"):
        triggered_signals.append(f"EXIF metadata indicates manipulation: {exif_res.get('summary')}")
    if not mrz_checksum_valid:
        triggered_signals.append("ICAO MRZ check-digit verification failed (strong tampering signal)")

    return {
        "tamper_risk_score": final_score,
        "is_high_risk": final_score >= 65.0,
        "is_medium_risk": 30.0 <= final_score < 65.0,
        "is_low_risk": final_score < 30.0,
        "triggered_signals": triggered_signals,
        "signal_breakdown": {
            "cnn_model": {
                "score": cnn_score,
                "weight": WEIGHT_CNN_MODEL,
                "status": onnx_res.get("status"),
                "tamper_probability": onnx_res.get("tamper_probability")
            },
            "error_level_analysis": {
                "score": ela_score,
                "weight": WEIGHT_ELA_DIFF,
                "flagged": ela_res.get("flagged"),
                "detail": ela_res.get("detail"),
                "heatmap_base64": ela_res.get("heatmap_base64"),
            },
            "exif_forensics": {
                "score": exif_score,
                "weight": WEIGHT_EXIF_FORENSICS,
                "flagged": exif_res.get("flagged"),
                "software_detected": exif_res.get("software_tag"),
                "flags": exif_res.get("flags")
            },
            "mrz_checksum": {
                "score": mrz_tamper_score,
                "weight": WEIGHT_MRZ_CHECKSUM,
                "checksum_valid": mrz_checksum_valid
            }
        }
    }
