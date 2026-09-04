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


def test_screen_endpoint_with_selfie_and_audit_persistence():
    doc_img = create_synthetic_passport_image()
    _, doc_enc = cv2.imencode(".jpg", doc_img)

    # Synthetic selfie image
    selfie_img = np.ones((200, 200, 3), dtype=np.uint8) * 180
    cv2.circle(selfie_img, (100, 100), 50, (150, 150, 150), -1)
    _, selfie_enc = cv2.imencode(".jpg", selfie_img)

    files = {
        "document_image": ("passport_with_selfie.jpg", doc_enc.tobytes(), "image/jpeg"),
        "live_selfie": ("traveler_selfie.jpg", selfie_enc.tobytes(), "image/jpeg"),
    }
    data = {
        "crop_mode": "auto",
        "force_crop": "true",
    }

    response = client.post("/screen", files=files, data=data)
    assert response.status_code == 200
    res = response.json()

    assert res["face_match"]["performed"] is True
    assert "is_match" in res["face_match"]
    assert isinstance(res["face_match"]["is_match"], bool)
    assert isinstance(res["face_match"]["match_score"], (int, float))
    assert res["face_match"]["match_status"] in ["pass", "not_sure", "mismatch"]

    # Verify audit persistence worked and didn't crash on json.dumps
    audit_id = res["audit_id"]
    audit_resp = client.get(f"/audit/{audit_id}")
    assert audit_resp.status_code == 200
    assert audit_resp.json()["id"] == audit_id


def test_calculate_icao_endpoint():
    # Test standard check digit calculation for passport number
    resp = client.post("/calculate-icao", json={
        "data_string": "W6734242",
        "weights": "7,3,1",
        "modulo": 10,
        "expected_check_digit": "8"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["computed_check_digit"] == "8"
    assert data["is_valid"] is True
    assert len(data["steps"]) == 8

    # Test custom weights and modulo
    resp_custom = client.post("/calculate-icao", json={
        "data_string": "12345",
        "weights": "3,1,7",
        "modulo": 11
    })
    assert resp_custom.status_code == 200
    custom_data = resp_custom.json()
    assert custom_data["weights"] == [3, 1, 7]
    assert custom_data["modulo"] == 11
    assert "formula_expression" in custom_data


def test_screen_with_manual_mrz_override():
    img = create_synthetic_passport_image()
    _, enc = cv2.imencode(".jpg", img)
    image_bytes = enc.tobytes()

    l1 = "P<INDBANSAL<<SMARTH<<<<<<<<<<<<<<<<<<<<<<<<<"
    l2 = "W6734242<8IND0804183M260417004C4102642022<18"

    files = {
        "document_image": ("smarth_passport.jpg", image_bytes, "image/jpeg")
    }
    data = {
        "manual_mrz_line1": l1,
        "manual_mrz_line2": l2,
        "icao_weights": "7,3,1",
        "icao_modulo": 10,
        "force_crop": "true"
    }

    response = client.post("/screen", files=files, data=data)
    assert response.status_code == 200
    res = response.json()

    assert res["mrz_checksum_valid"] is True
    assert res["extracted_fields"]["passport_number"]["value"] == "W6734242"
    assert res["extracted_fields"]["full_name"]["value"] == "SMARTH BANSAL"
    assert res["extracted_fields"]["nationality"]["value"] == "IND"
    assert res["extracted_fields"]["issuing_country"]["value"] == "IND"



