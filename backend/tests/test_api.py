import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.tests.test_modules import create_synthetic_passport_image

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "DocuVerify"
    assert "notice" in data


def test_screen_endpoint_with_valid_document():
    img = create_synthetic_passport_image()
    _, enc = cv2.imencode(".jpg", img)
    image_bytes = enc.tobytes()

    files = {
        "document_image": ("passport_test.jpg", image_bytes, "image/jpeg")
    }
    data = {
        "force_crop": "true"
    }

    response = client.post("/screen", files=files, data=data)
    assert response.status_code == 200
    res = response.json()

    # Verify response schema per prompt requirements
    assert "audit_id" in res
    assert "overall_recommendation" in res
    assert "tamper_risk_score" in res
    assert "tamper_signals" in res
    assert "extracted_fields" in res
    assert "mrz_checksum_valid" in res
    assert "validation" in res
    assert "scan_metadata" in res
    assert "human_officer_guidance" in res

    # Verify recommendation never auto-rejects
    assert any(res["overall_recommendation"].startswith(prefix) for prefix in ["LOW RISK", "MEDIUM", "HIGH"])

    # Test audit history endpoint persists this event
    hist_resp = client.get("/history")
    assert hist_resp.status_code == 200
    hist_list = hist_resp.json()
    assert len(hist_list) > 0
    assert any(entry["id"] == res["audit_id"] for entry in hist_list)

    # Test single audit inspect endpoint
    audit_resp = client.get(f"/audit/{res['audit_id']}")
    assert audit_resp.status_code == 200
    assert audit_resp.json()["id"] == res["audit_id"]


def test_screen_endpoint_scanner_error_on_invalid_image():
    # 100x100 square with no passport contours
    invalid_img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".jpg", invalid_img)

    files = {
        "document_image": ("random_photo.jpg", enc.tobytes(), "image/jpeg")
    }
    data = {
        "force_crop": "false"
    }

    response = client.post("/screen", files=files, data=data)
    assert response.status_code == 422
    err = response.json()
    assert err["error"] == "SCANNER_ERROR"
    assert "suggestion" in err


def test_screen_endpoint_with_crop_mode_and_photo_forensics():
    img = create_synthetic_passport_image()
    _, enc = cv2.imencode(".jpg", img)
    image_bytes = enc.tobytes()

    files = {
        "document_image": ("passport_bottom.jpg", image_bytes, "image/jpeg")
    }
    data = {
        "crop_mode": "bottom_half",
        "force_crop": "true"
    }

    response = client.post("/screen", files=files, data=data)
    assert response.status_code == 200
    res = response.json()

    assert "crop_method" in res["scan_metadata"]
    assert "photo_determination" in res["face_match"]
    assert "photo_risk_score" in res["face_match"]["photo_determination"]
    assert "splice_detected" in res["face_match"]["photo_determination"]
    assert "flags" in res["face_match"]["photo_determination"]

