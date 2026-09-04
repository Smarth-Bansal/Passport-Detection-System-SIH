import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "DocuVerify"
APP_DESCRIPTION = "AI-Powered Passport Screening & Tamper Detection Decision Support System"
APP_VERSION = "1.0.0"
MODEL_VERSION = "kaggle-mobilenetv3-tamper-v1.0"
KAGGLE_NOTEBOOK_REF = "docuverify/passport-tamper-detection-mobilenetv3"

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'docuverify.db'}")

# File and Model Paths
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "tamper_classifier.onnx"))
MOCK_BLACKLIST_PATH = os.getenv("MOCK_BLACKLIST_PATH", str(BASE_DIR / "data" / "mock_blacklist.csv"))

# Scanner aspect ratio tuning for ICAO TD3 passport bio-data page (125mm x 88mm = ~1.4205)
PASSPORT_ASPECT_RATIO = 1.4205
ASPECT_RATIO_TOLERANCE = 0.25  # range roughly [1.17, 1.67]

# Tamper Detection Ensemble Weights (sum = 1.0)
WEIGHT_CNN_MODEL = 0.35
WEIGHT_ELA_DIFF = 0.25
WEIGHT_EXIF_FORENSICS = 0.15
WEIGHT_MRZ_CHECKSUM = 0.25

# Risk Thresholds (Module 4: Tamper Risk Score >= 30 triggers HIGH — flag for secondary inspection)
TAMPER_RISK_LOW_MAX = 15.0
TAMPER_RISK_MEDIUM_MAX = 30.0
