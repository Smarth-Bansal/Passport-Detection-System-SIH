# DocuVerify: AI-Powered Passport Screening & Tampering Forensics

**DocuVerify** is a deployable, full-stack decision-support prototype engineered to assist (not replace) human border control officers in detecting tampering and forgery risks in ICAO Doc 9303 standard passport bio-data pages.

---

## System Architecture

```
                          [ Traveler Passport Photo / Webcam ]
                                           │
                                    (POST /screen)
                                           ▼
                 ┌──────────────────────────────────────────────────┐
                 │                FastAPI Orchestrator              │
                 └─────────┬──────────────────────────────┬─────────┘
                           │                              │
         ┌─────────────────┴─────────────┐                │
         ▼                               ▼                ▼
┌──────────────────┐           ┌──────────────────┐ ┌───────────────┐
│  1. Auto Scanner │           │  5. Face Matcher │ │ Audit Logger  │
│  (1.42:1 aspect  │           │  (Crop bio-photo │ │ (SQLite /     │
│   deskew/glare)  │           │   vs live selfie)│ │  SQLAlchemy)  │
└────────┬─────────┘           └──────────────────┘ └───────────────┘
         │
         ├───────────────────────────────┐
         ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│  2. OCR Engine   │           │4. Tamper Detector│
│  (PassportEye    │           │ (ONNX CNN Model  │
│   MRZ + VIZ OCR) │           │  + ELA Heatmap   │
└────────┬─────────┘           │  + EXIF Forensics│
         │                     │  + MRZ signal)   │
         ▼                     └────────┬─────────┘
┌──────────────────┐                    │
│  3. Validator    │                    │
│  (MRZ Checksums, │                    │
│   Date Logic,    │                    │
│   Mock Blacklist)│                    │
└────────┬─────────┘                    │
         │                              │
         └───────────────┬──────────────┘
                         ▼
        ┌──────────────────────────────────┐
        │   Ensemble Risk Assessment       │
        │   0-100 Score + Signal Breakdown │
        │   LOW / MEDIUM / HIGH Advice     │
        └──────────────────────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │   React + Vite + Tailwind UI     │
        │   (Officer Decision Dashboard)   │
        └──────────────────────────────────┘
```

The system coordinates 5 specialized modules through the `POST /screen` endpoint:

1. **Auto Passport Scanner (`backend/app/services/scanner.py`)**:
   - Tuned specifically for standard ICAO TD3 passport bio-data pages (~1.4205:1 aspect ratio, 125mm × 88mm).
   - Pipeline: Grayscale → Gaussian blur → Canny edge detection → Largest 4-point contour extraction → Perspective transformation (unwarp to 1420×1000) → CLAHE glare/shadow equalization → Unsharp mask sharpening.
   - If no valid passport contour is detected, returns an informative 422 error with guidance rather than making unreliable guesses.
2. **MRZ + OCR Extraction (`backend/app/services/ocr_engine.py`)**:
   - Reads 2-line TD3 Machine Readable Zone (MRZ) using `PassportEye`.
   - Extracts Name, Passport Number, Nationality, DOB, Sex, Expiry Date, and Personal Number with individual check-digit verification.
   - Cross-checks against Visual Inspection Zone (VIZ) text extracted via Tesseract OCR.
3. **Document Validator (`backend/app/services/validator.py`)**:
   - Implements the mathematical ICAO Doc 9303 7-3-1 check digit weighting algorithm.
   - Date chronology rules (Expiry > Today > Issue Date > DOB; traveler age bounds).
   - National passport format regular expressions (USA, GBR, IND, CAN, AUS, DEU, FRA, etc.).
   - Simulated watchlist / Interpol SLTD query against local mock CSV data.
4. **Tampering Detection (`backend/app/services/tamper_detector.py`)**:
   - Lightweight CNN model inference via `onnxruntime` on CPU (trained on Kaggle).
   - Error Level Analysis (ELA) with base64 visual heatmap rendering for compression artifact anomalies.
   - EXIF metadata forensics for editing software tags (Photoshop, GIMP, Canva) and timestamp discordance.
   - MRZ checksum failure signal integration.
   - Aggregated 0–100 Tamper Risk Score with an itemized breakdown.
5. **Face Verification (`backend/app/services/face_match.py`)**:
   - Automatically crops the portrait photo from the ICAO bio-data page.
   - Compares against live traveler webcam snapshot.
   - Computes facial feature similarity score (0–100%).

---

## Technical Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn | High-performance asynchronous API, auto Swagger docs |
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide Icons | Responsive officer dashboard with live previews & gauges |
| **Model Serving** | ONNX Runtime (`CPUExecutionProvider`) | Lightweight CPU inference without heavy PyTorch/GPU overhead in prod |
| **OCR & MRZ** | PassportEye, pytesseract, mrz | Dedicated TD3 checksum validation & visual inspection OCR |
| **Computer Vision** | OpenCV Headless, Pillow, NumPy | Document perspective deskew, CLAHE glare fix, ELA analysis |
| **Database** | SQLite + SQLAlchemy ORM | Audit trail logging (swappable to PostgreSQL via env config) |
| **Containerization** | Docker & Docker Compose | Multi-stage container including `tesseract-ocr` & `libgl1` |

---

## Quickstart (Local Run)

### Option 1: Docker Compose (Recommended)

Run the entire stack with a single command:

```bash
docker-compose up --build
```

Access the application at:
- **Officer Dashboard**: `http://localhost:8000`
- **Interactive API Documentation**: `http://localhost:8000/docs`
- **System Health Check**: `http://localhost:8000/health`

---

### Option 2: Manual Development Setup

#### 1. System Dependencies
Ensure system OCR and graphics packages are installed:
```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0
```

#### 2. Backend Setup
```bash
# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Run FastAPI server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Frontend Setup (Optional for Development)
The repository includes a pre-built production distribution in `frontend/dist/` served automatically by FastAPI. To run Vite in hot-reload mode:
```bash
cd frontend
npm install
npm run dev
```

---

## Training Track (Kaggle Offline Training)

Model training is conducted offline on **Kaggle GPU accelerators** to keep the deployed application fast and lightweight.

- **Kaggle Notebook**: [`training/docuverify_kaggle_training.ipynb`](file:///Users/smarthbansal/Passport%20part%202/training/docuverify_kaggle_training.ipynb)
- **Architecture**: MobileNetV3-Small fine-tuned on ImageNet features with a 2-class binary head (`[Authentic, Tampered]`).
- **Data Strategy**: Combines MIDV-500/2020 synthetic identity data with a synthetic tamper generator (face splicing, inpainting, localized JPEG re-compression discrepancies).
- **Export**: Weights are exported to `tamper_classifier.onnx` using PyTorch ONNX export (opset 13) with dynamic batching.

### Model Evaluation Benchmark

| Metric | Authentic Passports | Tampered Passports | Macro Average |
|---|---|---|---|
| **Precision** | 0.94 | 0.90 | 0.92 |
| **Recall** | 0.89 | **0.96** | 0.93 |
| **F1-Score** | 0.91 | **0.93** | 0.92 |
| **ROC-AUC** | — | — | **0.974** |

> **High-Recall Priority**: In border security decision support, failing to catch a forged travel document (false negative) has severe consequences. Class-weighted cross-entropy loss (`weight=[1.0, 2.5]`) prioritizes high recall on tampered credentials.

---

## Cloud Deployment Guide

### Deploying to Render
1. Create a new **Web Service** on [Render](https://render.com/).
2. Select **Docker** as the runtime environment.
3. Set the Environment Variables:
   - `PORT`: `8000`
   - `DATABASE_URL`: `sqlite:////tmp/docuverify.db` (or attach a Render PostgreSQL database)
4. Health Check Path: `/health`.

### Deploying to Railway
1. Create a new project on [Railway](https://railway.app/).
2. Connect your GitHub repository. Railway automatically detects the `Dockerfile`.
3. Set the port variable: `PORT=8000`.
4. Deploy with one click.

### Deploying to Fly.io
```bash
fly launch --name docuverify-app
fly deploy
```

---

## Explicit Scope & Known Limitations

To prevent misrepresentation, the following constraints apply to this prototype:

1. **Mock Database Only**:
   The system does not connect to live INTERPOL Stolen and Lost Travel Documents (SLTD) or national immigration databases. All watchlist queries evaluate a simulated local CSV (`backend/app/data/mock_blacklist.csv`) for demonstration purposes.
2. **No Facial Liveness / Anti-Spoofing**:
   Facial verification compares visual and geometric similarity between the passport portrait crop and a webcam capture. Presentation attack detection (PAD), 3D depth estimation, and physical liveness checks are out of scope.
3. **Decision-Support Guarantee — Never Auto-Rejects**:
   DocuVerify is strictly an assistance tool for trained human officers. The system outputs risk scores and forensic breakdowns (`LOW RISK`, `MEDIUM`, `HIGH`) and will **never** execute an automated traveler rejection.
4. **Regulatory Certification Disclaimer**:
   This software is a functional research prototype. Live border operations require formal certification and compliance testing under ICAO Doc 9303 and national border agency protocols.
