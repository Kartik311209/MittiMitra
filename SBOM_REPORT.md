# MittiMitra Project Report and Software Bill of Materials

**Document version:** 1.0  
**Report date:** 29 September 2026  
**Repository snapshot:** `a32a17e6fb9fc60d7c7bcb55f0b3f39d1a254052`  
**Application version:** `MittiMitra Farmer API 1.0.0`  
**Classification:** Academic project prototype. Not intended for production agricultural advisory use.

---

## 1. Executive summary

MittiMitra is an India-focused farmer-support project developed as a working prototype. Farmers can register through mobile OTP, add their land and location details, upload a soil image for an NPK estimate, find soil-lab links, view state-related scheme updates, explore land-lease opportunities, and use the Kisan Mitra AI assistant. The project also contains a crop-disease photo workflow. It only becomes available after a reviewed, licensed and labelled training dataset has been added locally.

The project is currently a **working Dockerized prototype**. The local dashboard and API have been verified at `http://localhost:8501` and `http://localhost:8000/docs` respectively. The soil NPK model is intentionally trained on synthetic data, so its output must be treated as an initial educational estimate - not a certified soil result or fertilizer prescription.

This document records what has been built, the software and services used, how farmer data is handled, and what still needs to be completed before any public launch. A screenshot of the current local portal is included on the first page as implementation evidence.

## 2. Scope and SBOM method

### Included in this report

- Application source in `dashboard.py` and `src/soil_npk/`
- Docker runtime configuration (`Dockerfile`, `docker-compose.yml`)
- Direct and transitive Python packages installed in the project virtual environment
- Bundled client assets and map libraries
- External runtime services, public data sources, and persistent data stores
- Implementation and delivery status as of this repository snapshot

### Not included

- Docker image digest and OS-level Debian package inventory; the Docker base is specified as the mutable tag `python:3.12-slim`, not a digest.
- `.env` secrets, SQLite contents, uploaded farmer photos, local generated training data, and temporary output files. These are deliberately ignored by Git.
- A live vulnerability/CVE scan. This report is an inventory and engineering review, not a security certification.

### Evidence used

- `requirements.txt`, Docker configuration, environment template, README, source inspection
- Installed package inventory from the local `.venv`
- `pip check` result: **No broken requirements found**
- Git commit listed above

## 3. What this project is working on

| Product area | Current objective |
|---|---|
| Soil intelligence | Provide a photo-based, explainable first estimate of NPK and moisture, then promote validation using a certified soil laboratory. |
| Crop disease detection | Provide a farmer crop-photo workflow that predicts a disease class or healthy status only after a locally trained labelled-image model is available. Training data will be selected from Kaggle only after source-license, crop coverage, label quality and India-field relevance checks. |
| Farmer access | Let a farmer register once, verify a mobile number with OTP, and return using OTP without entering all profile details again. |
| India-local support | Provide State -> District/City -> Tehsil -> Village selection and state-aware scheme information. |
| Farmer services | Help farmers find soil labs, update their details, opt into scheme messages, and discover land-lease opportunities. |
| Kisan Mitra AI | Offer voice/text agricultural, livestock-feed, and weather-aware crop guidance with guardrails. |
| Admin operations | Allow an authorized administrator to publish/remove official scheme updates for national or state audiences. |

## 4. Architecture and data flow

```text
Farmer browser
    |
    v
Streamlit dashboard (port 8501)
    | HTTP + session header
    v
FastAPI service (port 8000)
    |- SQLite: farmer profiles, OTP hashes, sessions, samples, lab values,
    |  scheme updates and lease listings
    |- Local filesystem: uploaded soil images, lab-labelled training CSV,
    |  trained NPK model artifact
    |- Crop-disease baseline: temporary farmer crop image -> confidence-aware
    |  preliminary class result; local Kaggle-sourced, license-reviewed training data
    |- Twilio Verify / Messaging Service: real OTP and opted-in SMS alerts
    |- Google Gemini: Kisan Mitra AI text, speech transcription and TTS
    |- Open-Meteo: forecast used only after farmer weather-consent
    `- Government / public links: LGD, Soil Health Card, MyScheme, PIB, DES
```

## 5. Primary software components

| Component | Version / identifier | Role | License / status |
|---|---:|---|---|
| MittiMitra dashboard | Repository source | Farmer and admin user interface | Project license not yet declared |
| MittiMitra API | `1.0.0` | Authentication, profiles, uploads, prediction, training, AI, scheme and lease APIs | Project license not yet declared |
| Python | `3.12` | Docker runtime | Python Software Foundation License (verify exact image contents on release) |
| Docker base image | `python:3.12-slim` | API and dashboard container base | Mutable tag; pin a digest before production |
| SQLite | Python standard library runtime | Local persistence | Public domain (SQLite); database file contains sensitive data |
| Highcharts Maps / Highmaps | `13.0.2` | Interactive India activity/agriculture map | **Commercial-license review required**; bundled header says a commercial license may be required |
| India map topology | `in-all.js`, `in-all-disputed.js` | State/UT boundaries for the interactive map | Review source terms together with Highcharts licensing |
| NumPy NPK model artifact | `artifacts/npk_baseline.npz` | Saved prototype regression model | Model derived from synthetic training data |

## 6. Direct Python dependency SBOM

These are the application-declared packages in `requirements.txt`. Exact versions below are the versions installed in the reviewed local environment; the requirement file uses `>=` ranges.

| Package | Declared requirement | Installed version | License expression from package metadata | Purpose |
|---|---|---:|---|---|
| `numpy` | `>=1.26` | `2.5.2` | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` | Image features, model arrays and regression calculations |
| `Pillow` | `>=10.0` | `12.3.0` | `MIT-CMU` | Soil image loading and processing |
| `fastapi` | `>=0.115` | `0.141.1` | `MIT` | HTTP backend and request validation |
| `uvicorn[standard]` | `>=0.30` | `0.52.4` | `BSD-3-Clause` | ASGI server |
| `streamlit` | `>=1.38` | `1.62.0` | `Apache-2.0` | Farmer/admin web dashboard |
| `python-multipart` | `>=0.0.9` | `0.0.32` | `Apache-2.0` | Multipart image and voice upload handling |
| `requests` | `>=2.32` | `2.34.2` | `Apache-2.0` | Twilio, Gemini, Open-Meteo and API calls |
| `python-dotenv` | `>=1.0` | `1.2.3` | `BSD-3-Clause` | Local `.env` loading |
| `openpyxl` | `>=3.1` | `3.1.5` | `MIT` | India district, tehsil and village XLSX imports |

## 7. Transitive Python runtime inventory

The following packages were installed in the reviewed `.venv`. They are included to make the dependency picture reproducible. Licensing of every transitive package should be automatically checked again in a CI license-scanning job before any public release.

| Package | Version | Package | Version | Package | Version |
|---|---:|---|---:|---|---:|
| altair | 6.2.2 | annotated-doc | 0.0.5 | annotated-types | 0.8.0 |
| anyio | 4.14.2 | attrs | 26.1.0 | blinker | 1.9.0 |
| certifi | 2026.7.22 | charset-normalizer | 3.5.1 | click | 8.5.0 |
| et_xmlfile | 2.0.0 | h11 | 0.16.0 | httptools | 0.8.0 |
| idna | 3.19 | itsdangerous | 2.2.0 | Jinja2 | 3.1.6 |
| jsonschema | 4.26.0 | jsonschema-specifications | 2025.9.1 | MarkupSafe | 3.0.3 |
| narwhals | 2.25.0 | packaging | 26.3 | pandas | 3.0.5 |
| protobuf | 7.36.0 | pyarrow | 25.0.1 | pydantic | 2.13.5 |
| pydantic_core | 2.46.5 | pydeck | 0.9.3 | python-dateutil | 2.9.0.post0 |
| PyYAML | 6.0.3 | referencing | 0.37.0 | rpds-py | 2026.6.3 |
| six | 1.17.0 | starlette | 1.6.0 | toml | 0.10.2 |
| typing_extensions | 4.16.0 | typing-inspection | 0.4.4 | tzdata | 2026.3 |
| urllib3 | 2.7.0 | watchdog | 6.0.0 | websockets | 16.1.1 |

Build-only tooling present: `pip 25.0.1`.

## 8. Bundled assets, models, and datasets

| Asset / dataset | Location | Use | Source / compliance note |
|---|---|---|---|
| Soil hero imagery and dashboard screenshots | `assets/*.png` | Dashboard visual design | Confirm ownership/permission before public distribution if any asset was imported from a third party. |
| Highcharts Maps bundle | `assets/maps/highmaps.js` | Browser map renderer | See licensing warning in section 5. |
| India map topology | `assets/maps/in-all.js`, `assets/maps/in-all-disputed.js` | Interactive boundary map | Maintain attribution and confirm terms before release. |
| India district workbook | `All_Districtof_India_*.xlsx` | Cascading location data bootstrap | Review/update source and license periodically. |
| India sub-district workbook | `All_Sub_Districtof_India_*.xlsx` | Tehsil dropdown bootstrap | Review/update source and license periodically. |
| India village workbook | `All_Villagesof_India_*.xlsx` | Village dropdown bootstrap | Contains large public location data; review source terms and freshness. |
| Synthetic NPK image generator | `src/soil_npk/generator.py` | Reproducible synthetic training examples | Built in-project. |
| Baseline model | `artifacts/npk_baseline.npz` | Prototype NPK prediction | Not lab validated; do not make accuracy or fertilizer-dose claims. |
| Crop-disease training dataset | `data/crop_disease/raw/` local folder; exact Kaggle dataset not yet selected/downloaded | Crop disease classifier training | Verify Kaggle license, dataset owner, permitted use, labels, classes and attribution before download or training. Raw images are Git-ignored. |
| Crop-disease model artifact | `artifacts/crop_disease_baseline.npz` after training | Preliminary crop image class prediction | Nearest-centroid labelled-image baseline; must remain a prototype until independently field validated. |
| Local app database | `data/app_data/terranpk.db` | PII and operational records | Git-ignored; must never be committed or shared publicly. |

## 9. External services and data sources

| Service / source | Data exchanged | Current role | Configuration / caution |
|---|---|---|---|
| Twilio Verify | Indian mobile number and OTP verification request | Real-time OTP when configured | Requires account SID, auth token and Verify Service SID; not configured in local runtime. |
| Twilio Messaging Service | Opted-in phone number and scheme message | Scheme SMS alerts | Use only explicit farmer consent; requires messaging SID. |
| Google Gemini | Farmer question; voice data for transcription; answer text for TTS | Kisan Mitra AI | Keep API key server-side. Follow Google terms, quotas and data-use settings. |
| Open-Meteo | Registered district and state | 7-day weather-informed advice | Dashboard requires consent before weather request. |
| LGD / Ministry of Panchayati Raj | State, district, tehsil, village directory | Location data import reference | Refresh only from official current export. |
| Soil Health Card portal | District/state lab lookup link | Nearest laboratory guidance | Link-out, not a local laboratory directory. |
| MyScheme / PIB / government departmental links | Public web links | Scheme information and official references | Admin must validate every published scheme link and deadline. |
| DES / Economic Survey statistics | PM-KISAN and agriculture-GSVA context | India map tooltips | Snapshot values are contextual only, not live farmer counts or eligibility decisions. |
| Google Maps search URL | District/state search query in the user browser | Lab discovery convenience link | User browser leaves the application for Google Maps. |

## 10. Persistent data and privacy inventory

| Data category | Stored fields / behavior | Storage | Sensitivity |
|---|---|---|---|
| Farmer identity and contact | Name, Indian mobile number, age, land area/unit | SQLite | Personal data |
| Farmer address | Village, tehsil/city, district, state | SQLite | Sensitive location/profile data |
| Preferences | Scheme-SMS and small-landholder-update opt-ins | SQLite | Consent record |
| Authentication | OTP hashes, session tokens and expiry timestamps | SQLite | Security-sensitive; do not expose/log |
| Soil samples | Uploaded image, original filename, prediction, linked lab values | Filesystem + SQLite | Potentially personal/agricultural data |
| Crop disease photos | One uploaded crop image, returned disease class/confidence and safe next step | Ephemeral temporary file only | The API deletes the photo after its response; it does not add the image to NPK training data. |
| Lab-validated labels | N, P, K values linked to a sample | SQLite and exported training CSV | Agricultural data; becomes approved model-training data |
| Lease listings and interest | Land details, location, period, crop preference, note and interest record | SQLite | Sensitive commercial/location data |
| Voice input | Sent to AI transcription endpoint when the farmer submits it | Not intended to be saved by this app | External AI provider processing applies |

### Data handling implemented

- `.env`, `data/app_data/`, generated/real data, virtual environment and temporary artifacts are ignored by Git.
- Screen OTP uses a short TTL and a hashed code for local development; it is explicitly not suitable for a public deployment.
- Uploaded photo estimates are **not** automatically used as training truth. A certified lab result is required before an image enters the labelled training export.
- Auto-retraining begins at the configurable threshold of **20** certified image-plus-lab examples.

## 11. Completed implementation status

| Feature | Status | Evidence / delivered behaviour |
|---|---|---|
| Dockerized dashboard + API | **Completed** | `docker compose up -d` starts the Streamlit dashboard and FastAPI service. |
| Soil photo upload and NPK estimate | **Completed as prototype** | Image features feed the saved NumPy baseline, returning N/P/K, moisture and conservative recommendation signals. |
| Synthetic data generator + retraining workflow | **Completed as prototype** | Generator, training module, certified-lab-result capture and threshold-based retraining are implemented. |
| Crop disease detection from a farmer photo | **Implemented; model training required** | Authenticated farmer UI, status endpoint and `POST /crop-disease/predict` accept JPG/PNG/WEBP crop images up to 8 MB. The temporary photo is deleted after inference and results contain class, confidence, safe next step and expert-review warning. |
| Kaggle crop-disease training dataset | **Planned / dataset not yet selected** | A Kaggle dataset will be used only after license, author/source, crop/disease class balance, label quality and India-field relevance are reviewed. |
| Clear scientific disclaimer | **Completed** | UI and README state that visual estimates are not laboratory results. |
| Farmer registration + returning login | **Completed** | New farmer profile flow and returning farmer OTP flow are available. |
| Real SMS integration path | **Implemented; deployment configuration pending** | Twilio Verify and Messaging integrations exist; credentials must be configured for real delivery. |
| Safe local OTP demo mode | **Completed** | `OTP_DELIVERY_MODE=screen` enables local demonstration without SMS. |
| India cascading location selection | **Completed** | States/UTs plus district, tehsil and village endpoints bootstrapped from included XLSX files. |
| Multi-language interface | **Completed for Hindi, Hinglish and English** | Three interface modes are manually translated. Other Indian languages are not yet fully translated. |
| State/UT agriculture map | **Completed as data snapshot** | Interactive map supports state/UT tooltips for active local registrations, PM-KISAN snapshot, GVA share, crops and soils. |
| State-targeted scheme updates | **Completed** | Active update API filters by farmer state; admin can publish/remove verified updates. |
| SMS scheme opt-in | **Completed in code; messaging configuration pending** | Consent fields, confirmation and targeted messaging paths are implemented. |
| Profile editing | **Completed** | Farmer can update identity, land and location information after login. |
| Nearby soil laboratory support | **Completed as official/map link-out** | Directs farmer to Soil Health Card and a district/state Google Maps search. |
| Land-lease module | **Completed as marketplace prototype** | Listing, browse, interest registration, consent, and displayed 48% owner / 48% cultivator / 4% platform split are implemented. |
| Kisan Mitra AI | **Completed in code; provider configuration required** | Text, voice transcription, optional spoken reply, livestock guidance and consent-gated weather advice use Gemini/Open-Meteo. |
| Separate admin login | **Completed** | `SCHEME_ADMIN_KEY` protects the scheme-update management interface. |

## 12. API inventory

### Public / farmer flow

- `GET /health`
- `GET /locations/states`, `/locations/districts`, `/locations/tehsils`, `/locations/villages`
- `GET /farmer-activity`
- `GET /scheme-updates/active`
- `POST /auth/request-otp`
- `POST /auth/verify-otp`
- `POST /auth/verify-returning-otp`

### Authenticated farmer flow (`X-Session-Token`)

- `GET /me`, `PUT /me`
- `POST /samples`, `POST /samples/{sample_id}/lab-results`, `GET /model-status`
- `GET /crop-disease/status`, `POST /crop-disease/predict`
- `GET /lease-listings`, `POST /lease-listings`, `POST /lease-listings/{listing_id}/interest`
- `POST /assistant/advice`, `POST /assistant/transcribe`, `POST /assistant/speak`

### Admin flow (`X-Scheme-Admin-Key`)

- `POST /admin/scheme-notifications`
- `GET /admin/scheme-updates`
- `POST /admin/scheme-updates`
- `DELETE /admin/scheme-updates/{update_id}`

## 13. Security, operational and licensing findings

| Priority | Finding | Why it matters | Recommended action |
|---|---|---|---|
| High | Highcharts Maps has a commercial-license warning in the bundled file. | Public/commercial use may require a paid Highsoft license. | Obtain the required license or replace the map renderer/data with a compatible open-source alternative before launch. |
| High | The NPK model is synthetic-data based. | Agricultural advice could harm a farmer if treated as a lab result. | Keep the current disclaimers, prohibit dosage claims, and validate against a field-level lab test set before any accuracy claim. |
| High | Farmer PII and exact locations are stored locally in SQLite. | Leakage, loss or unauthorized access can affect farmers. | Encrypt backups/storage, add retention/deletion policy, access logs, least privilege and a privacy notice/consent record. |
| High | Real OTP, Gemini and scheme SMS depend on third-party secrets. | Missing/weak secrets break services or create abuse risk. | Store secrets in a managed vault, rotate them, set strong admin keys, rate-limit OTP/API endpoints and never commit `.env`. |
| Medium | Dependency requirements use `>=` versions and Docker uses a mutable tag. | Builds can change over time and introduce new vulnerabilities. | Generate a lockfile/SBOM in CI; pin Python dependencies and Docker base image digest. |
| Medium | No CVE scan is included in this review. | Dependency vulnerabilities may be unknown. | Add Dependabot/Renovate plus `pip-audit` or OSV scanning to CI. |
| Medium | Local SQLite is single-node storage. | It is not a durable multi-user production database or backup strategy. | Move production data to a managed database, use migrations, backups, encryption and monitoring. |
| Medium | User-provided images and voice content reach server/provider endpoints. | Requires abuse protection and data processing controls. | Enforce server-side size/type checks, malware scanning/re-encoding, rate limits, privacy terms and provider-data review. |
| High | Crop-disease workflow is implemented, but no exact Kaggle dataset/license has been approved and no trained production model exists. | Dataset terms may restrict commercial use; labels may be biased, incomplete or unrelated to Indian field conditions. | Select a dataset only after recording its Kaggle URL, version, license, author, checksum, crop/disease classes and permitted-use evidence. Keep the raw data out of Git if it is large or restricted. |
| High | Crop-disease predictions could be mistaken for a confirmed diagnosis or pesticide recommendation. | Incorrect identification may lead to crop loss or unsafe chemical use. | Present a confidence-aware preliminary result, request better photos when needed, prohibit pesticide dosage recommendations, and direct high-risk/low-confidence cases to KVK/agriculture experts. |
| Medium | Lease matching facilitates real financial/land arrangements. | Legal, fraud, land-title and dispute risks exist. | Add KYC/title verification, state-law review, written agreements, grievance workflow and clear platform terms before activation. |
| Low | Current dashboard offers three fully authored language modes. | It does not yet meet a claim of full Indian-language support. | Add reviewed translations and language-specific voice UX before claiming nationwide multilingual coverage. |
| Low | Government statistics are snapshots. | A static value can become stale and should not imply live official data. | Display source date prominently and implement an approved refresh process. |

## 14. Remaining work before production release

1. **Licensing:** declare a project license, clear all image/map/data rights, and resolve Highcharts commercial licensing.
2. **Security:** rate-limit OTP and upload endpoints, add audit logging, HTTPS-only deployment, security headers, secure secret management, backups and deletion/export requests.
3. **Data protection:** publish a privacy policy, consent language, retention schedule and farmer data-access/deletion process.
4. **Model validation:** collect representative, consented, certified lab-labelled images; create train/validation/test splits by field; report MAE per region/soil/crop; obtain agricultural-domain review.
5. **Crop disease validation:** choose a Kaggle dataset with compatible terms; document the source and license; remove duplicates/leakage; split by plant/farm where possible; evaluate per crop/disease class; validate on Indian field images; calibrate the implemented confidence threshold and expert escalation before launch.
6. **OTP/SMS:** configure verified Indian sender/route, Twilio credentials and monitoring; keep screen OTP restricted to local development.
7. **AI safety:** configure Gemini in a controlled account; add prompt logging/redaction policy, evaluation cases, emergency escalation phrases and usage limits.
8. **Weather:** retain explicit consent and clarify that forecasts are advisory only; consider district/coordinate precision and a provider fallback.
9. **Admin operations:** provision a proper role-based admin account system rather than sharing one static key; require source/date review for each update.
10. **Testing and CI:** add unit/API/e2e tests, dependency scans, secret scans, SBOM generation and Docker-image scanning in GitHub Actions.
11. **GitHub release:** configure a GitHub remote and valid authentication, then push the existing initial commit. The repository currently has no configured remote in this snapshot.

## 15. Acceptance statement

MittiMitra is ready to be demonstrated locally as a **Dockerized agricultural-assistance prototype**. It is not ready to be marketed as a clinical/agronomic diagnostic, official government service, land-lease intermediary, or production SMS/AI platform until the release actions in section 14 are completed and independently verified.

---

### Reproducibility commands

```powershell
# Start the local prototype
docker compose up -d

# Open dashboard
Start-Process http://localhost:8501

# Verify Python dependency consistency
.\.venv\Scripts\python.exe -m pip check

# Inspect commit used for this report
git rev-parse HEAD
```

**Owner note:** Update this report whenever a dependency, base image, map/data asset, external provider, trained model, or deployment environment changes.
