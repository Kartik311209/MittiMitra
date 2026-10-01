# MittiMitra Project Report

**Project name:** MittiMitra - Farmer Support and Soil Intelligence Portal  
**Report date:** 29 September 2026  
**Project type:** Academic prototype  
**Technology:** Streamlit, FastAPI, Python, SQLite, Docker and NumPy

## 1. Introduction

MittiMitra is a farmer-support web portal created to keep useful farming information and simple digital tools in one place. The portal is designed for Indian farmers and supports Hindi, Hinglish and English. A farmer can sign in with an OTP, save land and address information, upload a soil photograph for an initial NPK estimate, view scheme updates, find soil-testing resources and use an AI assistant for general farming questions.

The purpose of the project is not to replace an agriculture officer, laboratory or veterinarian. It is a prototype that makes the first digital step easier for a farmer and directs the user to proper verification where required.

## 2. Problem Statement

Farmers often need information from several different places: soil-test laboratories, scheme portals, local agriculture offices, weather services and experienced advisors. Small farmers may also find it difficult to keep their land details, support links and crop information in one usable system. MittiMitra brings these tasks into a single portal while keeping important warnings visible.

## 3. Main Objectives

- Create a simple farmer login and registration flow using an Indian mobile number and OTP.
- Collect useful farmer details such as age, land size, land unit, state, district, tehsil and village.
- Provide a prototype soil-photo analysis workflow for NPK and moisture estimates.
- Show government scheme updates relevant to the farmer's registered state.
- Provide links for nearby soil-test laboratories and official agricultural resources.
- Offer Kisan Mitra AI for text and voice questions about farming, livestock feed and weather-aware crop planning.
- Add a safe crop-disease photo workflow that can be trained later using a reviewed Kaggle dataset.

## 4. System Architecture

```text
Farmer browser
      |
      v
Streamlit dashboard (port 8501)
      |
      | HTTP requests with session token
      v
FastAPI backend (port 8000)
      |
      +-- SQLite database: farmer profiles, OTP hashes, sessions and records
      +-- Local storage: soil uploads, approved lab labels and model files
      +-- NumPy/Pillow: prototype image feature extraction and prediction
      +-- Twilio: real OTP and opted-in scheme SMS when configured
      +-- Gemini and Open-Meteo: Kisan Mitra AI and consent-based weather guidance
```

The dashboard and API run as separate Docker services. The dashboard sends a session token only after successful OTP verification. The API checks this token before returning profile information, upload results, land-lease listings or AI guidance.

## 5. Implemented Modules

| Module | What it does | Current state |
|---|---|---|
| Farmer registration and login | New farmer registration and returning farmer login through a mobile OTP. | Implemented; screen OTP is available for local demo and Twilio can be configured for real SMS. |
| Farmer profile | Stores name, age, land area/unit and State -> District/City -> Tehsil -> Village details. | Implemented; farmers can update their saved information. |
| Soil NPK analysis | Accepts a soil photo and returns prototype N, P, K and moisture estimates. | Implemented as a synthetic-data prototype; lab confirmation is required. |
| Verified lab workflow | Lets the farmer attach certified lab values to a soil image for future NPK model retraining. | Implemented. |
| Scheme updates | Shows national and state-specific scheme notices and supports explicit SMS opt-in. | Implemented; real SMS needs Twilio credentials. |
| Soil laboratory support | Opens official Soil Health Card resources and district/state map search links. | Implemented as official link-out support. |
| Land lease support | Lets landholders list interest and farmers browse nearby opportunities. The displayed proposal is 48% landholder, 48% cultivator and 4% platform coordination. | Marketplace prototype; no payment, title transfer or legal agreement is performed. |
| Kisan Mitra AI | Provides text, voice, livestock-feed and consent-based local-weather queries. | Implemented; Gemini key is required for live AI use. |
| Crop disease check | Takes a crop photo and returns a preliminary class/confidence result only after a labelled model has been trained. | Workflow implemented; dataset and field validation are still required. |
| Admin portal | Allows an authorized administrator to add or remove verified scheme updates. | Implemented; protected by an admin key. |

## 6. Important Technology and SBOM Summary

This is a short software inventory for the project. It includes the main components that are important for development, deployment and future maintenance rather than a full dependency audit.

| Component | Use in MittiMitra |
|---|---|
| Python 3.12 | Main backend and data-processing runtime used by Docker. |
| Streamlit | Farmer and admin web interface. |
| FastAPI and Uvicorn | REST API, OTP flow, file uploads and protected routes. |
| SQLite | Local storage for farmers, sessions, scheme updates and operational records. |
| NumPy and Pillow | Image features, prototype models and photo handling. |
| Docker Compose | Starts the dashboard and API together. |
| OpenPyXL | Imports the India district, tehsil and village workbook data. |
| Twilio Verify / Messaging | Real OTP and opted-in scheme SMS after deployment configuration. |
| Google Gemini | Kisan Mitra AI text, voice transcription and optional spoken answer. |
| Open-Meteo | Weather forecast for a farmer who gives explicit consent. |

## 7. Data Handling and Safety

The project stores farmer identity, mobile number, land information and location in a local SQLite database. Soil-image uploads are saved for the NPK workflow only when needed, and a photo becomes part of future NPK training only after a certified laboratory result is entered. The crop-disease endpoint is different: it uses a temporary file and removes the crop photo after the result is returned.

The NPK model is trained on synthetic data, so its estimate is shown only as an educational prototype. The crop-disease feature is also deliberately conservative: it is unavailable without a reviewed labelled dataset, provides confidence-aware preliminary output, and does not suggest pesticide dosage. A real deployment must use HTTPS, secure secrets, rate limits, backup controls and a written privacy policy.

## 8. Current Status

The local project includes source code for the Streamlit dashboard, FastAPI backend, database workflow, Docker configuration, farmer account flow, scheme updates, map data, labs, land lease and Kisan Mitra AI. The crop-disease workflow and its training command have also been added. The remaining configuration work is mainly real SMS credentials, a reviewed crop-disease dataset, field validation and production security controls.

## 9. Future Scope

- Train and evaluate the crop-disease model using a Kaggle dataset with a suitable licence and India-relevant field images.
- Add field-level validation, accuracy metrics and feedback from agricultural experts for both image-based features.
- Integrate a verified Indian SMS route for OTP and scheme notifications.
- Move production data from local SQLite to a managed database with backups and access controls.
- Add role-based admin accounts, audit logging, rate limiting and a farmer privacy/deletion policy.
- Publish the Dockerized project to a secure HTTPS hosting environment.

## 10. Conclusion

MittiMitra is a complete academic prototype for combining farmer registration, soil-photo analysis, scheme support, land details, laboratory discovery, land-lease interest and AI-based guidance in one portal. The present version is ready for local demonstration and further model development. It should be treated as a prototype until the listed validation, privacy, security and service-configuration work is completed.
