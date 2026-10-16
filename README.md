<div align="center">

<img src="assets/logo.png" alt="MittiMitra Logo" width="120" />

# 🌱 MittiMitra — Farmer Support & Soil Intelligence Portal

**AI-powered soil NPK analysis · Farmer login with OTP · Kisan Mitra AI assistant · Government scheme updates**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.62-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

🌐 **Live Demo:** [mittimitra-web.vercel.app](https://mittimitra-web.vercel.app/)

</div>

---

## 📖 What is MittiMitra?

**MittiMitra** ("Friend of the Soil") is an academic prototype farmer-support portal built for Indian farmers. It brings together soil testing, scheme discovery, AI assistance, and land-lease support in one place — with full support for **Hindi, Hinglish, and English**.

> ⚠️ **Scientific Note:** Camera RGB images cannot replace lab nutrient testing. The included NPK model is trained on synthetic data and its output is a **prototype estimate only**, not a certified result.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔐 **OTP Farmer Login** | Register & log in with Indian mobile number + short-lived OTP |
| 🪴 **Soil NPK Analysis** | Upload a soil photo → get prototype N, P, K & moisture estimates |
| 🧪 **Lab Verification Workflow** | Attach certified lab values to trigger automatic model retraining |
| 🤖 **Kisan Mitra AI** | Gemini-powered farming assistant with voice, Hindi, and quick-chip support |
| 🌦️ **Weather Guidance** | Consent-based 5-day forecast via Open-Meteo |
| 📜 **Government Schemes** | National & state-specific scheme updates with optional SMS opt-in |
| 🗺️ **India Address Dropdowns** | State → District → Tehsil → Village using official LGD data |
| 🌿 **Crop Disease Check** | Photo-based preliminary crop disease detection (model training required) |
| 📊 **Admin Portal** | Scheme management behind an admin key |
| 🏡 **Land Lease Marketplace** | Browse/list land-lease interest (no payment or legal transfer) |

---

## 🏗️ Architecture

```
Farmer Browser
      │
      ▼
Streamlit Dashboard  (port 8501)
      │  HTTP + session token
      ▼
FastAPI Backend      (port 8000)
      ├── SQLite        — farmer profiles, OTPs, sessions, records
      ├── Local FS      — soil image uploads, lab labels, model files
      ├── NumPy/Pillow  — image feature extraction & NPK prediction
      ├── Twilio        — real SMS OTP & scheme notifications (optional)
      ├── Google Gemini — Kisan Mitra AI assistant
      └── Open-Meteo   — consent-based weather forecasts
```

---

## 🚀 Quick Start (Local)

### 1. Prerequisites
- Python 3.12+
- PowerShell (Windows) or bash (Linux/macOS)

### 2. Setup

```powershell
# Clone the repo
git clone https://github.com/Kartik311209/MittiMitra.git
cd MittiMitra

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate           # Linux/macOS

pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
```

### 3. Generate synthetic data & train

```powershell
python -m soil_npk.generator --samples 800
python -m soil_npk.training
```

### 4. Run the app

**Terminal 1 — Dashboard:**
```powershell
python -m streamlit run dashboard.py
```

**Terminal 2 — API backend:**
```powershell
uvicorn soil_npk.api:app --reload
```

- Dashboard: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

---

## 🐳 Docker (Recommended)

```powershell
Copy-Item .env.example .env
# Edit .env with your keys (see OTP section below)
docker compose up --build
```

- Dashboard: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# OTP delivery — use 'screen' for local dev, 'twilio' for production
OTP_DELIVERY_MODE=screen

# Required for production SMS OTP
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_VERIFY_SERVICE_SID=VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# AI assistant
GEMINI_API_KEY=your_gemini_api_key

# Admin portal
SCHEME_ADMIN_KEY=your_secret_admin_key
```

> 🛡️ **Never commit your `.env` file.** It is already listed in `.gitignore`.

---

## 📱 OTP Modes

| Mode | When to use | How it works |
|---|---|---|
| `screen` | Local development | OTP appears as a yellow banner on the dashboard — no SMS sent |
| `twilio` | Production | Real SMS sent to farmer's mobile via Twilio Verify |

---

## 🧪 Run Tests

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

---

## 📂 Project Layout

```
MittiMitra/
├── dashboard.py              # Streamlit UI (farmer portal + admin)
├── hosted_app.py             # Single-port ASGI entry for Render deployment
├── src/soil_npk/
│   ├── api.py                # FastAPI routes (OTP, upload, farmer, schemes)
│   ├── farmer_service.py     # OTP logic, farmer CRUD, lab-label workflow
│   ├── assistant_service.py  # Kisan Mitra AI (Gemini + weather + KB)
│   ├── model.py              # NPK prediction model
│   ├── training.py           # Model retraining pipeline
│   ├── crop_disease.py       # Crop disease baseline
│   └── locations.py          # LGD address data
├── data/
│   ├── kb/                   # Crop knowledge base markdown files
│   ├── schemes.json          # Government scheme directory
│   └── locations/            # LGD district/tehsil/village data
├── artifacts/                # Trained model files (git-ignored)
├── web/                      # Static landing page (Vercel)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Core backend runtime |
| Streamlit | Farmer & admin web interface |
| FastAPI + Uvicorn | REST API, file uploads, protected routes |
| SQLite | Local database (farmers, sessions, records) |
| NumPy + Pillow | Image features & prototype NPK model |
| Docker Compose | Multi-service local & production deployment |
| OpenPyXL | India LGD district/village workbook import |
| Twilio Verify | Real SMS OTP & scheme notifications |
| Google Gemini | Kisan Mitra AI assistant |
| Open-Meteo | Consent-based weather forecast |

---

## 🌿 Crop Disease Check

After login, farmers can upload a crop photo for preliminary disease detection. The feature is intentionally **disabled until a validated model** is available.

To train a candidate model (research only — does not activate the portal):

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m soil_npk.crop_disease `
    --dataset-dir .\data\crop_disease\prepared `
    --model-path .\artifacts\crop_disease_candidate.npz
```

> Low-confidence results must be verified by a KVK, agriculture officer, or qualified agronomist. The app **never** recommends a pesticide or dosage from a photo.

---

## 🔭 Future Scope

- [ ] Train & validate crop-disease model on India-relevant Kaggle field images
- [ ] Integrate verified Indian SMS route for OTP + scheme SMS
- [ ] Migrate SQLite → managed PostgreSQL with backups
- [ ] Add role-based admin accounts, audit logging, and rate limiting
- [ ] HTTPS production deployment with farmer data privacy/deletion policy
- [ ] Mandi price integration (currently links to AGMARKNET)
- [ ] Offline-first mobile client with queued form submissions

---

## 📄 License

This project is an **academic prototype** built for demonstration purposes.

---

## 🙏 Acknowledgements

- [Government of India LGD](https://data.gov.in/catalog/local-government-directory-lgd) — district, tehsil & village data
- [Open-Meteo](https://open-meteo.com/) — free weather forecast API
- [Streamlit](https://streamlit.io) — rapid UI for Python
- Kisan Call Centre — 1800-180-1551

---

<div align="center">
Made with ❤️ for Indian farmers &nbsp;·&nbsp; <a href="https://mittimitra-web.vercel.app/">Live Demo</a>
</div>
