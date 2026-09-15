"""FastAPI backend for OTP login, soil uploads, and verified-data retraining."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Docker Compose supplies environment variables directly. For a normal local
# `uvicorn` run, load the project's ignored `.env` file before app modules read
# their settings. Existing system environment variables keep priority.
load_dotenv(PROJECT_ROOT / ".env")

from .government_data import (
    AGRICULTURE_GSVA_SHARE_2023_24,
    AGRICULTURE_GSVA_SHARE_SOURCE,
    PM_KISAN_20TH_INSTALLMENT_AS_OF,
    PM_KISAN_20TH_INSTALLMENT_BENEFICIARIES,
    PM_KISAN_20TH_INSTALLMENT_SOURCE,
    STATE_AGRI_PROFILES,
)
from .farmer_service import (
    MODEL_PATH,
    SMSConfigurationError,
    SMSProviderError,
    active_farmers_by_state,
    active_scheme_updates,
    all_scheme_updates,
    add_lab_result,
    add_prediction,
    create_otp,
    create_lease_listing,
    create_scheme_update,
    create_session,
    farmer_for_phone,
    farmer_for_token,
    initialise_database,
    model_status,
    notify_opted_in_farmers,
    deactivate_scheme_update,
    express_lease_interest,
    lease_listings,
    otp_delivery_mode,
    retrain_if_ready,
    save_sample,
    send_scheme_opt_in_confirmation,
    update_farmer,
    upsert_farmer,
    verify_otp,
)
from .prediction import predict_image
from .locations import districts, initialise_locations, location_status, states, tehsils, villages
from .assistant_service import (
    AssistantConfigurationError,
    AssistantProviderError,
    answer_farmer_question,
    synthesize_assistant_voice,
    transcribe_farmer_voice,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialise_database()
    initialise_locations()
    yield


app = FastAPI(title="MittiMitra Farmer API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        item
        for item in os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",")
        if item
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=PROJECT_ROOT / "assets"), name="assets")


class OTPRequest(BaseModel):
    phone_number: str


class FarmerProfile(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=14, le=120)
    land_size: float = Field(gt=0, le=100000)
    land_unit: str = Field(min_length=2, max_length=80)
    village: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=120)
    tehsil: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    phone_number: str
    scheme_sms_opt_in: bool = False
    small_farm_updates: bool = False


class FarmerProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=14, le=120)
    land_size: float = Field(gt=0, le=100000)
    land_unit: str = Field(min_length=2, max_length=80)
    village: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=120)
    tehsil: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    scheme_sms_opt_in: bool = False
    small_farm_updates: bool = False


class OTPVerification(FarmerProfile):
    otp: str = Field(pattern=r"^\d{4,8}$")


class ReturningOTPVerification(OTPRequest):
    otp: str = Field(pattern=r"^\d{4,8}$")


class LabResult(BaseModel):
    nitrogen_kg_ha: float = Field(ge=0, le=1000)
    phosphorus_kg_ha: float = Field(ge=0, le=1000)
    potassium_kg_ha: float = Field(ge=0, le=2000)
    moisture_percent: float | None = Field(default=None, ge=0, le=100)


class SchemeNotification(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    official_url: str = Field(pattern=r"^https://")
    small_farm_only: bool = False
    target_state: str | None = Field(default=None, max_length=120)


class SchemeUpdate(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    summary: str = Field(min_length=10, max_length=600)
    official_url: str = Field(pattern=r"^https://")
    target_state: str | None = Field(default=None, max_length=120)
    deadline: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class LeaseListing(BaseModel):
    land_size: float = Field(gt=0, le=100000)
    land_unit: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=120)
    tehsil: str = Field(min_length=2, max_length=120)
    village: str = Field(min_length=2, max_length=120)
    duration_months: int = Field(ge=6, le=60)
    crop_preference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    language: str = Field(default="Hindi", max_length=40)
    request_type: str = Field(default="general", pattern=r"^(general|livestock|crop_weather)$")


class AssistantSpeech(BaseModel):
    text: str = Field(min_length=2, max_length=3500)


def current_farmer(x_session_token: Annotated[str | None, Header()] = None) -> dict[str, object]:
    if not x_session_token:
        raise HTTPException(401, "Please log in first.")
    farmer = farmer_for_token(x_session_token)
    if not farmer:
        raise HTTPException(401, "Your login has expired. Request a new OTP.")
    return farmer


def require_scheme_admin(x_scheme_admin_key: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("SCHEME_ADMIN_KEY", "")
    if not expected or x_scheme_admin_key != expected:
        raise HTTPException(401, "Scheme admin authorization is required.")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok", "data_mode": "prototype", "otp_delivery_mode": otp_delivery_mode(),
        **model_status(), **location_status(),
    }


@app.get("/locations/states")
def location_states() -> dict[str, object]:
    return {"items": states()}


@app.get("/locations/districts")
def location_districts(state: str) -> dict[str, object]:
    return {"items": districts(state)}


@app.get("/locations/tehsils")
def location_tehsils(state: str, district: str) -> dict[str, object]:
    return {"items": tehsils(state, district)}


@app.get("/locations/villages")
def location_villages(state: str, district: str, tehsil: str) -> dict[str, object]:
    return {"items": villages(state, district, tehsil)}


@app.get("/farmer-activity")
def farmer_activity() -> dict[str, object]:
    """Public aggregate only: no farmer names, phones, or location details."""
    counts = active_farmers_by_state()
    return {
        "items": [
            {
                "state": state,
                "active_farmers": counts.get(state, 0),
                "pm_kisan_beneficiaries": PM_KISAN_20TH_INSTALLMENT_BENEFICIARIES.get(state, 0),
                "key_crops": STATE_AGRI_PROFILES.get(state, ("Data pending", "Data pending"))[0],
                "common_soils": STATE_AGRI_PROFILES.get(state, ("Data pending", "Data pending"))[1],
                "agriculture_gsva_share_percent": AGRICULTURE_GSVA_SHARE_2023_24.get(state),
            }
            for state in states()
        ],
        "definition": "A farmer with at least one valid, unexpired MittiMitra sign-in session.",
        "historical_pm_kisan": {
            "as_of": PM_KISAN_20TH_INSTALLMENT_AS_OF,
            "source_url": PM_KISAN_20TH_INSTALLMENT_SOURCE,
            "definition": "PM-KISAN beneficiaries covered under the 20th instalment; this is not MittiMitra user data.",
        },
        "india_agriculture_gva_share_percent": 17.8,
        "india_agriculture_gva_year": "2023-24",
        "state_agriculture_gsva": {"year": "2023-24", "source_url": AGRICULTURE_GSVA_SHARE_SOURCE},
    }


@app.get("/scheme-updates/active")
def public_scheme_updates(state: str | None = None) -> dict[str, object]:
    return {"items": active_scheme_updates(state.strip() if state else None)}


@app.post("/auth/request-otp")
def request_otp(payload: OTPRequest) -> dict[str, str]:
    try:
        return create_otp(payload.phone_number)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except SMSConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except SMSProviderError as error:
        raise HTTPException(502, f"SMS could not be delivered: {error}") from error


@app.post("/auth/verify-otp")
def login(payload: OTPVerification) -> dict[str, object]:
    try:
        valid = verify_otp(payload.phone_number, payload.otp)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except SMSConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except SMSProviderError as error:
        raise HTTPException(502, f"OTP could not be verified: {error}") from error
    if not valid:
        raise HTTPException(401, "OTP is invalid or has expired.")
    try:
        farmer = upsert_farmer(payload.model_dump(exclude={"otp"}))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        scheme_sms_status = send_scheme_opt_in_confirmation(farmer)
    except SMSProviderError:
        # A marketing/update SMS issue must not block an already verified farmer from logging in.
        scheme_sms_status = "delivery_failed"
    return {"session_token": create_session(str(farmer["id"])), "farmer": farmer, "scheme_sms_status": scheme_sms_status}


@app.post("/auth/verify-returning-otp")
def login_returning_farmer(payload: ReturningOTPVerification) -> dict[str, object]:
    """Log in a farmer already registered against their verified mobile number."""
    try:
        valid = verify_otp(payload.phone_number, payload.otp)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except SMSConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except SMSProviderError as error:
        raise HTTPException(502, f"OTP could not be verified: {error}") from error
    if not valid:
        raise HTTPException(401, "OTP is invalid or has expired.")
    try:
        farmer = farmer_for_phone(payload.phone_number)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not farmer:
        raise HTTPException(404, "No farmer profile exists for this mobile number. Please register first.")
    return {"session_token": create_session(str(farmer["id"])), "farmer": farmer}


@app.get("/me")
def me(farmer: Annotated[dict[str, object], Depends(current_farmer)]) -> dict[str, object]:
    return farmer


@app.put("/me")
def update_my_profile(
    payload: FarmerProfileUpdate,
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
) -> dict[str, object]:
    """A signed-in farmer may correct land and location details; OTP mobile remains verified."""
    try:
        return update_farmer(str(farmer["id"]), payload.model_dump())
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


@app.get("/lease-listings")
def available_lease_listings(
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
    state: str | None = None,
    district: str | None = None,
) -> dict[str, object]:
    """Verified users can browse nearby listings; owner phone numbers are never returned."""
    return {"items": lease_listings(state.strip() if state else None, district.strip() if district else None), "viewer_id": farmer["id"]}


@app.post("/lease-listings")
def add_lease_listing(
    payload: LeaseListing,
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
) -> dict[str, object]:
    return create_lease_listing(str(farmer["id"]), payload.model_dump())


@app.post("/lease-listings/{listing_id}/interest")
def request_lease_information(
    listing_id: str,
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
) -> dict[str, object]:
    try:
        return express_lease_interest(listing_id, str(farmer["id"]))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/assistant/advice")
def kisan_mitra_advice(
    payload: AssistantQuestion,
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
) -> dict[str, object]:
    """AI guidance. Forecast lookup only happens for an explicit crop-weather request."""
    try:
        return answer_farmer_question(payload.question, farmer, payload.language, payload.request_type)
    except AssistantConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except AssistantProviderError as error:
        raise HTTPException(502, str(error)) from error


@app.post("/assistant/transcribe")
async def transcribe_kisan_voice(
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
    audio: UploadFile = File(...),
    language: str = Form("Hindi"),
) -> dict[str, str]:
    """Convert a farmer's explicitly recorded question to text; the file is never saved."""
    _ = farmer
    try:
        transcript = transcribe_farmer_voice(await audio.read(), audio.filename or "farmer-question.wav", audio.content_type or "audio/wav", language)
    except ValueError as error:
        raise HTTPException(413, str(error)) from error
    except AssistantConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except AssistantProviderError as error:
        raise HTTPException(502, str(error)) from error
    return {"transcript": transcript}


@app.post("/assistant/speak")
def speak_kisan_mitra_answer(
    payload: AssistantSpeech,
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
) -> dict[str, str]:
    """Create an ephemeral Gemini voice reply; audio is returned directly and not stored."""
    _ = farmer
    try:
        return {"audio_base64": synthesize_assistant_voice(payload.text), "mime_type": "audio/wav"}
    except AssistantConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except AssistantProviderError as error:
        raise HTTPException(502, str(error)) from error


@app.post("/samples")
async def upload_sample(
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
    image: UploadFile = File(...),
) -> dict[str, object]:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG, or WEBP soil image.")
    contents = await image.read()
    if not contents or len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be between 1 byte and 10 MB.")
    if not MODEL_PATH.exists():
        raise HTTPException(503, "Model missing. Generate data and train the model first.")
    sample_id, image_path = save_sample(str(farmer["id"]), image.filename or "soil.jpg", image.content_type, contents)
    try:
        prediction = predict_image(image_path, MODEL_PATH)
        add_prediction(sample_id, json.dumps(prediction))
    except Exception:
        image_path.unlink(missing_ok=True)
        raise
    return {
        "sample_id": sample_id,
        "prediction": prediction,
        "training_status": "Saved safely. Add a certified lab N/P/K result to make this image eligible for automatic retraining.",
    }


@app.post("/samples/{sample_id}/lab-results")
def attach_lab_result(
    sample_id: str,
    payload: LabResult,
    farmer: Annotated[dict[str, object], Depends(current_farmer)],
) -> dict[str, object]:
    try:
        add_lab_result(sample_id, str(farmer["id"]), payload.model_dump())
        training = retrain_if_ready()
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return {"sample_id": sample_id, "training": training}


@app.get("/model-status")
def get_model_status(_: Annotated[dict[str, object], Depends(current_farmer)]) -> dict[str, object]:
    return model_status()


@app.post("/admin/scheme-notifications")
def publish_scheme_notification(
    payload: SchemeNotification,
    _: Annotated[None, Depends(require_scheme_admin)],
) -> dict[str, int]:
    return notify_opted_in_farmers(payload.title, payload.official_url, payload.small_farm_only, payload.target_state)


@app.get("/admin/scheme-updates")
def list_scheme_updates(_: Annotated[None, Depends(require_scheme_admin)]) -> dict[str, object]:
    return {"items": all_scheme_updates()}


@app.post("/admin/scheme-updates")
def publish_scheme_update(payload: SchemeUpdate, _: Annotated[None, Depends(require_scheme_admin)]) -> dict[str, object]:
    update = payload.model_dump()
    update["target_state"] = update["target_state"] or None
    return create_scheme_update(update)


@app.delete("/admin/scheme-updates/{update_id}")
def remove_scheme_update(update_id: str, _: Annotated[None, Depends(require_scheme_admin)]) -> dict[str, bool]:
    return {"deactivated": deactivate_scheme_update(update_id)}
