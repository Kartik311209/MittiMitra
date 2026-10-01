# Soil NPK Analysis Using AI & ML

Public preview: [MittiMitra on Vercel](https://mittimitra-web.vercel.app/).
The static landing page is in [`web/`](web/).
It is intentionally separate from the farmer portal. The portal needs a
container host, persistent database/uploads, real SMS OTP, and HTTPS before a
public launch; local screen OTP is for development only.
For the complete single-port portal and a password-protected, disposable test
deployment, see [HOSTING.md](HOSTING.md).

A synthetic-data MVP that estimates Nitrogen (N), Phosphorus (P), and Potassium (K) from a soil image. It is designed so future field images and matching laboratory reports can be used with the same training contract.

> **Scientific limitation:** camera RGB images cannot replace laboratory nutrient testing. The included model learns deliberately created relationships in synthetic images, so its outputs are prototype estimates only.

## Features

- Reproducible synthetic soil image and label generator
- Actual multi-output ML baseline predicting N, P, and K in kg/ha
- Explainable low/medium/high nutrient flags and conservative demo recommendations
- Streamlit dashboard and FastAPI prediction endpoint
- Stable CSV schema for future lab-validated data
- Farmer profile login: name, age, land area/unit, village, district, city, state and mobile OTP
- Persistent SQLite storage for farmer records and uploaded soil photos
- Automatic retraining after enough uploaded images have **certified laboratory N/P/K labels**

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
```

## Run the MVP

```powershell
python -m soil_npk.generator --samples 800
python -m soil_npk.training
python -m streamlit run dashboard.py
```

In a second terminal, run the backend before using the dashboard login/upload flow:

```powershell
uvicorn soil_npk.api:app --reload
```

Visit `http://127.0.0.1:8000/docs` to test the API.

## Run with Docker

Docker Desktop must be running. Build and start both the dashboard and API:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://localhost:8501`. The API docs are at `http://localhost:8000/docs`.

For local, free testing, set `OTP_DELIVERY_MODE=screen` in `.env`: the short-lived OTP appears only on the local dashboard and no SMS is sent. Never use this mode on a public deployment. Real SMS OTP uses Twilio Verify: set `OTP_DELIVERY_MODE=twilio`, create a Verify Service, put its Account SID, Auth Token and Verify Service SID in `.env`, then restart the API container. Keep `.env` private and serve a public deployment over HTTPS.

Farmers can separately opt in to government-scheme SMS updates and choose small-landholder updates. An opt-in confirmation is sent through the configured Twilio Messaging Service. An admin can publish a verified official update through `POST /admin/scheme-notifications` using the `X-Scheme-Admin-Key` header. The app never labels someone as poor from land size, and it never promises scheme eligibility; each scheme's official rules determine that.

### India address dropdowns

The registration order is **State → District/City → Tehsil → Village**. States and UTs are built in; the lower levels are served from a server-side copy of the Government of India Local Government Directory (LGD), rather than bundling hundreds of thousands of village names in the browser. Follow [data/locations/README.md](data/locations/README.md) once to import the official current export. The LGD directory is maintained by the Ministry of Panchayati Raj and its current catalogue is published on the [Government of India OGD platform](https://data.gov.in/catalog/local-government-directory-lgd).

### Upload and automatic learning

Every soil image upload is saved under `data/app_data/uploads/` with the farmer account and the model prediction. It is **not** used as NPK training data just because it is a photo: a photo has no ground-truth nutrient value. When a certified lab report is entered for that same sample, the server exports it to the training dataset. At 20 verified image + lab-report samples (configurable with `MIN_LABELED_SAMPLES`), every new verified result automatically retrains and replaces the baseline model.

This protects farmers from a misleading feedback loop where an earlier photo estimate is treated as if it were a real lab result.

### Crop disease check (labelled-photo baseline)

After login, farmers also have a **Crop disease check**. It accepts one JPG,
PNG or WEBP crop photo and displays the predicted labelled class, confidence,
and a safe next step directly below that photo. The temporary crop photo is
deleted by the API after the response; it is not silently added to the NPK
training set.

The feature deliberately stays unavailable until a crop-photo model has been
trained and validated on relevant field images. Five Indian field-photo source
archives have been prepared locally for research; they do **not** cover all
Indian crops or agro-climatic zones. Their origin, label limitations, licence
notes and candidate training/evaluation commands are documented in
[data/crop_disease/README.md](data/crop_disease/README.md).

For a research-only candidate that does not activate the portal, run:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m soil_npk.crop_disease --dataset-dir .\data\crop_disease\prepared --model-path .\artifacts\crop_disease_candidate.npz
.\.venv\Scripts\python.exe -m soil_npk.evaluate_crop_disease --model-path .\artifacts\crop_disease_candidate.npz --test-dir .\data\crop_disease\prepared\test --report-path .\artifacts\crop_disease_candidate_evaluation.json
```

The supplied model is a transparent image-similarity baseline, not a confirmed
disease diagnosis. Low-confidence and non-healthy results must be verified by
a KVK, agriculture officer, or qualified agronomist; the app never recommends
a pesticide or dosage from a photo alone.

## Future real-data migration

Create a CSV with at least these columns:

```text
image_path,nitrogen_kg_ha,phosphorus_kg_ha,potassium_kg_ha
```

`image_path` is relative to the CSV file. Optional fields are `sample_id`, `soil_type`, `ph`, `moisture_percent`, `district`, and `collection_date`. Do not merge a future real set into the synthetic test split: keep an untouched, field-level test set and report its MAE before making any accuracy claim.

For real data, replace the handcrafted baseline with transfer learning (for example EfficientNet) while keeping the API response and CSV contract unchanged. Fine-tune only after images are paired with certified lab values.

## Project layout

```text
src/soil_npk/       generator, features, model, training, API
data/synthetic/     generated images and labels (ignored by git)
artifacts/          trained model file (ignored by git)
dashboard.py        user interface
```
