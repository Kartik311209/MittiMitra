"""Persistent farmer, OTP, upload, and lab-label workflow for the API.

An uploaded image is kept as an *unlabelled* example. It can improve an NPK
model only after a certified lab result is attached; a photo has no true NPK
target by itself.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from .training import train


APP_DATA_DIR = Path(os.getenv("NPK_APP_DATA_DIR", "data/app_data"))
DATABASE_PATH = Path(os.getenv("NPK_DATABASE_PATH", str(APP_DATA_DIR / "terranpk.db")))
UPLOAD_DIR = APP_DATA_DIR / "uploads"
TRAINING_DIR = APP_DATA_DIR / "training"
MODEL_PATH = Path(os.getenv("NPK_MODEL_PATH", "artifacts/npk_baseline.npz"))
MIN_LABELED_SAMPLES = int(os.getenv("MIN_LABELED_SAMPLES", "20"))
LOCAL_OTP_TTL_SECONDS = int(os.getenv("LOCAL_OTP_TTL_SECONDS", "300"))
LOCAL_OTP_MAX_ATTEMPTS = int(os.getenv("LOCAL_OTP_MAX_ATTEMPTS", "5"))


class SMSConfigurationError(RuntimeError):
    """The deployment has not been given the real SMS provider credentials."""


class SMSProviderError(RuntimeError):
    """The SMS provider could not create or validate a verification."""


def now() -> datetime:
    return datetime.now(UTC)


def normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D", "", phone_number)
    if len(digits) == 10:
        digits = f"91{digits}"
    if len(digits) != 12 or not digits.startswith("91") or digits[2] not in "6789":
        raise ValueError("Enter a valid Indian 10-digit mobile number.")
    return f"+{digits}"


def _connection() -> sqlite3.Connection:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS farmers (
                id TEXT PRIMARY KEY, phone_number TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL,
                age INTEGER NOT NULL, land_size REAL NOT NULL, land_unit TEXT NOT NULL,
                village TEXT NOT NULL, district TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL,
                scheme_sms_opt_in INTEGER NOT NULL DEFAULT 0, small_farm_updates INTEGER NOT NULL DEFAULT 0,
                scheme_sms_confirmed_at TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, farmer_id TEXT NOT NULL, expires_at TEXT NOT NULL,
                FOREIGN KEY(farmer_id) REFERENCES farmers(id)
            );
            CREATE TABLE IF NOT EXISTS local_otps (
                phone_number TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS samples (
                id TEXT PRIMARY KEY, farmer_id TEXT NOT NULL, image_path TEXT NOT NULL,
                original_filename TEXT NOT NULL, content_type TEXT NOT NULL, uploaded_at TEXT NOT NULL,
                nitrogen_kg_ha REAL, phosphorus_kg_ha REAL, potassium_kg_ha REAL,
                moisture_percent REAL, lab_recorded_at TEXT, prediction_json TEXT,
                FOREIGN KEY(farmer_id) REFERENCES farmers(id)
            );
            CREATE TABLE IF NOT EXISTS scheme_updates (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL, official_url TEXT NOT NULL,
                target_state TEXT, deadline TEXT, active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lease_listings (
                id TEXT PRIMARY KEY, farmer_id TEXT NOT NULL,
                land_size REAL NOT NULL, land_unit TEXT NOT NULL,
                state TEXT NOT NULL, district TEXT NOT NULL, tehsil TEXT NOT NULL, village TEXT NOT NULL,
                duration_months INTEGER NOT NULL, crop_preference TEXT, notes TEXT,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(farmer_id) REFERENCES farmers(id)
            );
            CREATE TABLE IF NOT EXISTS lease_interest (
                id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, farmer_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(listing_id, farmer_id),
                FOREIGN KEY(listing_id) REFERENCES lease_listings(id),
                FOREIGN KEY(farmer_id) REFERENCES farmers(id)
            );
            """
        )
        existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(farmers)")}
        if "scheme_sms_opt_in" not in existing_columns:
            connection.execute("ALTER TABLE farmers ADD COLUMN scheme_sms_opt_in INTEGER NOT NULL DEFAULT 0")
        if "small_farm_updates" not in existing_columns:
            connection.execute("ALTER TABLE farmers ADD COLUMN small_farm_updates INTEGER NOT NULL DEFAULT 0")
        if "scheme_sms_confirmed_at" not in existing_columns:
            connection.execute("ALTER TABLE farmers ADD COLUMN scheme_sms_confirmed_at TEXT")
        # A verified starter notice; it automatically disappears after its deadline.
        connection.execute(
            """INSERT OR IGNORE INTO scheme_updates(id, title, summary, official_url, target_state, deadline, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            ("official-pmfby-up-2026-kharif", "PMFBY Kharif 2026 — Uttar Pradesh", "Eligible KCC farmers can check enrolment with their bank or insurer.", "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2298726&lang=2&reg=48", "Uttar Pradesh", "2026-08-31", now().isoformat(), now().isoformat()),
        )


def _twilio_settings() -> tuple[str, str, str]:
    settings = (
        os.getenv("TWILIO_ACCOUNT_SID", ""),
        os.getenv("TWILIO_AUTH_TOKEN", ""),
        os.getenv("TWILIO_VERIFY_SERVICE_SID", ""),
    )
    if not all(settings):
        raise SMSConfigurationError(
            "Real SMS OTP is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_VERIFY_SERVICE_SID."
        )
    return settings


def otp_delivery_mode() -> str:
    """Select a safe local demonstrator or Twilio's real-SMS delivery."""
    mode = os.getenv("OTP_DELIVERY_MODE", "twilio").strip().lower()
    if mode not in {"screen", "twilio"}:
        raise SMSConfigurationError("OTP_DELIVERY_MODE must be either 'screen' or 'twilio'.")
    return mode


def _local_otp_hash(phone_number: str, code: str) -> str:
    secret = os.getenv("OTP_SCREEN_SECRET", "local-development-only")
    return hashlib.sha256(f"{phone_number}:{code}:{secret}".encode("utf-8")).hexdigest()


def _create_screen_otp(phone_number: str) -> dict[str, str]:
    """Create a short-lived local OTP for a private development screen only."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = now() + timedelta(seconds=LOCAL_OTP_TTL_SECONDS)
    with _connection() as connection:
        connection.execute(
            """INSERT INTO local_otps(phone_number, code_hash, expires_at, attempts, created_at)
            VALUES (?, ?, ?, 0, ?)
            ON CONFLICT(phone_number) DO UPDATE SET code_hash=excluded.code_hash,
            expires_at=excluded.expires_at, attempts=0, created_at=excluded.created_at""",
            (phone_number, _local_otp_hash(phone_number, code), expires_at.isoformat(), now().isoformat()),
        )
    # This field is intentionally returned only in OTP_DELIVERY_MODE=screen.
    return {"phone_number": phone_number, "delivery": "screen", "status": "pending", "otp": code}


def _verify_screen_otp(phone_number: str, code: str) -> bool:
    with _connection() as connection:
        row = connection.execute("SELECT * FROM local_otps WHERE phone_number=?", (phone_number,)).fetchone()
        if not row:
            return False
        expired = datetime.fromisoformat(str(row["expires_at"])) <= now()
        attempts_exhausted = int(row["attempts"]) >= LOCAL_OTP_MAX_ATTEMPTS
        if expired or attempts_exhausted:
            connection.execute("DELETE FROM local_otps WHERE phone_number=?", (phone_number,))
            return False
        valid = hmac.compare_digest(str(row["code_hash"]), _local_otp_hash(phone_number, code))
        if valid:
            connection.execute("DELETE FROM local_otps WHERE phone_number=?", (phone_number,))
        else:
            connection.execute("UPDATE local_otps SET attempts=attempts+1 WHERE phone_number=?", (phone_number,))
        return valid


def _twilio_post(path: str, values: dict[str, str]) -> dict[str, Any]:
    account_sid, auth_token, service_sid = _twilio_settings()
    response = requests.post(
        f"https://verify.twilio.com/v2/Services/{service_sid}/{path}",
        data=values,
        auth=(account_sid, auth_token),
        timeout=15,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        message = str(payload.get("message", "SMS provider request failed."))
        raise SMSProviderError(message)
    return payload


def create_otp(phone_number: str) -> dict[str, str]:
    phone_number = normalize_phone(phone_number)
    if otp_delivery_mode() == "screen":
        return _create_screen_otp(phone_number)
    verification = _twilio_post("Verifications", {"To": phone_number, "Channel": "sms"})
    if verification.get("status") != "pending":
        raise SMSProviderError("SMS verification could not be started.")
    return {"phone_number": phone_number, "delivery": "sms", "status": "pending"}


def verify_otp(phone_number: str, code: str) -> bool:
    phone_number = normalize_phone(phone_number)
    if otp_delivery_mode() == "screen":
        return _verify_screen_otp(phone_number, code)
    verification = _twilio_post("VerificationCheck", {"To": phone_number, "Code": code})
    return verification.get("status") == "approved"


def send_scheme_opt_in_confirmation(farmer: dict[str, Any]) -> str:
    """Send one consent confirmation; scheme eligibility is never inferred here."""
    if not farmer.get("scheme_sms_opt_in"):
        return "not_requested"
    with _connection() as connection:
        confirmed = connection.execute("SELECT scheme_sms_confirmed_at FROM farmers WHERE id=?", (farmer["id"],)).fetchone()
    if confirmed and confirmed["scheme_sms_confirmed_at"]:
        return "already_confirmed"
    if not os.getenv("TWILIO_MESSAGING_SERVICE_SID", ""):
        return "messaging_not_configured"
    small_holder = " Chhoti joat updates bhi selected hain." if farmer.get("small_farm_updates") else ""
    status = _send_sms(
        str(farmer["phone_number"]),
        "MittiMitra: Aapne government scheme SMS updates ke liye consent diya hai. Sirf official updates bheje jayenge; eligibility sarkari rules se tay hoti hai." + small_holder,
    )
    if status == "queued":
        with _connection() as connection:
            connection.execute("UPDATE farmers SET scheme_sms_confirmed_at=? WHERE id=?", (now().isoformat(), farmer["id"]))
    return status


def _send_sms(phone_number: str, body: str) -> str:
    """Send a consented non-OTP SMS through the configured Messaging Service."""
    account_sid, auth_token, _ = _twilio_settings()
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")
    if not messaging_service_sid:
        return "messaging_not_configured"
    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data={
            "To": phone_number,
            "MessagingServiceSid": messaging_service_sid,
            "Body": body,
        },
        auth=(account_sid, auth_token),
        timeout=15,
    )
    if not response.ok:
        try:
            message = response.json().get("message", "Scheme SMS could not be sent.")
        except ValueError:
            message = "Scheme SMS could not be sent."
        raise SMSProviderError(str(message))
    return "queued"


def notify_opted_in_farmers(title: str, official_url: str, small_farm_only: bool, target_state: str | None = None) -> dict[str, int]:
    """Deliver a verified update to only farmers who explicitly opted in."""
    query = "SELECT * FROM farmers WHERE scheme_sms_opt_in=1"
    parameters: list[str] = []
    if small_farm_only:
        query += " AND small_farm_updates=1"
    if target_state:
        query += " AND state=?"
        parameters.append(target_state)
    with _connection() as connection:
        farmers = [dict(row) for row in connection.execute(query, parameters).fetchall()]
    queued = failed = 0
    for farmer in farmers:
        try:
            if _send_sms(str(farmer["phone_number"]), f"MittiMitra Government update: {title}. Official information: {official_url}") == "queued":
                queued += 1
        except SMSProviderError:
            failed += 1
    return {"recipients": len(farmers), "queued": queued, "failed": failed}


def create_scheme_update(update: dict[str, Any]) -> dict[str, Any]:
    """Save a verified official update. A past deadline is never returned publicly."""
    update_id, timestamp = secrets.token_urlsafe(12), now().isoformat()
    record = {**update, "id": update_id, "created_at": timestamp, "updated_at": timestamp}
    with _connection() as connection:
        connection.execute(
            """INSERT INTO scheme_updates(id, title, summary, official_url, target_state, deadline, active, created_at, updated_at)
            VALUES(:id, :title, :summary, :official_url, :target_state, :deadline, 1, :created_at, :updated_at)""",
            record,
        )
    return {**record, "active": True}


def active_scheme_updates(state: str | None = None) -> list[dict[str, Any]]:
    """Return national plus matching state updates, excluding expired deadlines."""
    query = """SELECT * FROM scheme_updates WHERE active=1
        AND (deadline IS NULL OR date(deadline) >= date('now'))"""
    parameters: list[str] = []
    if state:
        query += " AND (target_state IS NULL OR target_state=?)"
        parameters.append(state)
    else:
        # Before OTP login the farmer's state is unknown, so never leak a state-only notice.
        query += " AND target_state IS NULL"
    query += " ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline ASC, created_at DESC"
    with _connection() as connection:
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def all_scheme_updates() -> list[dict[str, Any]]:
    with _connection() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM scheme_updates ORDER BY active DESC, created_at DESC").fetchall()]


def deactivate_scheme_update(update_id: str) -> bool:
    with _connection() as connection:
        result = connection.execute("UPDATE scheme_updates SET active=0, updated_at=? WHERE id=?", (now().isoformat(), update_id))
    return result.rowcount == 1


def create_lease_listing(farmer_id: str, listing: dict[str, Any]) -> dict[str, Any]:
    """Create a lease opportunity; legal agreement and verification happen offline."""
    listing_id, timestamp = secrets.token_urlsafe(12), now().isoformat()
    record = {**listing, "id": listing_id, "farmer_id": farmer_id, "created_at": timestamp, "updated_at": timestamp}
    with _connection() as connection:
        connection.execute(
            """INSERT INTO lease_listings(
                id, farmer_id, land_size, land_unit, state, district, tehsil, village,
                duration_months, crop_preference, notes, active, created_at, updated_at
            ) VALUES(
                :id, :farmer_id, :land_size, :land_unit, :state, :district, :tehsil, :village,
                :duration_months, :crop_preference, :notes, 1, :created_at, :updated_at
            )""",
            record,
        )
    return {**record, "active": True, "interest_count": 0}


def lease_listings(state: str | None = None, district: str | None = None, farmer_id: str | None = None) -> list[dict[str, Any]]:
    """Return location-level opportunities without exposing owner phone numbers."""
    query = """SELECT l.*, f.full_name AS owner_name, COUNT(i.id) AS interest_count
        FROM lease_listings l JOIN farmers f ON f.id=l.farmer_id
        LEFT JOIN lease_interest i ON i.listing_id=l.id
        WHERE l.active=1"""
    params: list[Any] = []
    if state:
        query += " AND l.state=?"
        params.append(state)
    if district:
        query += " AND l.district=?"
        params.append(district)
    if farmer_id:
        query += " AND l.farmer_id=?"
        params.append(farmer_id)
    query += " GROUP BY l.id ORDER BY l.created_at DESC"
    with _connection() as connection:
        return [dict(row) for row in connection.execute(query, params).fetchall()]


def express_lease_interest(listing_id: str, farmer_id: str) -> dict[str, Any]:
    """Record only a verified farmer's interest; no lease or payment is executed."""
    with _connection() as connection:
        listing = connection.execute("SELECT farmer_id, active FROM lease_listings WHERE id=?", (listing_id,)).fetchone()
        if not listing or not int(listing["active"]):
            raise ValueError("This lease opportunity is no longer available.")
        if str(listing["farmer_id"]) == farmer_id:
            raise ValueError("You cannot request your own listing.")
        connection.execute(
            "INSERT OR IGNORE INTO lease_interest(id, listing_id, farmer_id, created_at) VALUES (?, ?, ?, ?)",
            (secrets.token_urlsafe(12), listing_id, farmer_id, now().isoformat()),
        )
        count = connection.execute("SELECT COUNT(*) FROM lease_interest WHERE listing_id=?", (listing_id,)).fetchone()[0]
    return {"listing_id": listing_id, "interest_count": int(count), "status": "interest_recorded"}


def upsert_farmer(profile: dict[str, Any]) -> dict[str, Any]:
    farmer_id = secrets.token_urlsafe(16)
    saved_at = now().isoformat()
    profile = {
        **profile,
        "phone_number": normalize_phone(str(profile["phone_number"])),
        "city": profile["tehsil"],
        "scheme_sms_opt_in": bool(profile.get("scheme_sms_opt_in", False)),
        "small_farm_updates": bool(profile.get("small_farm_updates", False) and profile.get("scheme_sms_opt_in", False)),
    }
    with _connection() as connection:
        existing = connection.execute("SELECT id FROM farmers WHERE phone_number = ?", (profile["phone_number"],)).fetchone()
        if existing:
            farmer_id = existing["id"]
        connection.execute(
            """INSERT INTO farmers(id, phone_number, full_name, age, land_size, land_unit, village, district, city, state, scheme_sms_opt_in, small_farm_updates, created_at, updated_at)
            VALUES (:id, :phone_number, :full_name, :age, :land_size, :land_unit, :village, :district, :city, :state, :scheme_sms_opt_in, :small_farm_updates, :created_at, :updated_at)
            ON CONFLICT(phone_number) DO UPDATE SET full_name=excluded.full_name, age=excluded.age,
            land_size=excluded.land_size, land_unit=excluded.land_unit, village=excluded.village,
            district=excluded.district, city=excluded.city, state=excluded.state,
            scheme_sms_opt_in=excluded.scheme_sms_opt_in, small_farm_updates=excluded.small_farm_updates, updated_at=excluded.updated_at""",
            {**profile, "id": farmer_id, "created_at": saved_at, "updated_at": saved_at},
        )
    return {"id": farmer_id, **profile}


def update_farmer(farmer_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Update a verified farmer's profile without changing the verified phone number."""
    saved_at = now().isoformat()
    fields = {
        "full_name": str(profile["full_name"]).strip(), "age": int(profile["age"]),
        "land_size": float(profile["land_size"]), "land_unit": str(profile["land_unit"]).strip(),
        "village": str(profile["village"]).strip(), "district": str(profile["district"]).strip(),
        "city": str(profile["tehsil"]).strip(), "state": str(profile["state"]).strip(),
        "scheme_sms_opt_in": bool(profile.get("scheme_sms_opt_in", False)),
        "small_farm_updates": bool(profile.get("small_farm_updates", False) and profile.get("scheme_sms_opt_in", False)),
        "updated_at": saved_at, "id": farmer_id,
    }
    with _connection() as connection:
        connection.execute(
            """UPDATE farmers SET full_name=:full_name, age=:age, land_size=:land_size, land_unit=:land_unit,
            village=:village, district=:district, city=:city, state=:state,
            scheme_sms_opt_in=:scheme_sms_opt_in, small_farm_updates=:small_farm_updates, updated_at=:updated_at
            WHERE id=:id""",
            fields,
        )
        row = connection.execute("SELECT * FROM farmers WHERE id=?", (farmer_id,)).fetchone()
    if not row:
        raise ValueError("Farmer profile was not found.")
    return dict(row)


def create_session(farmer_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expiry = now() + timedelta(days=30)
    with _connection() as connection:
        connection.execute("INSERT INTO sessions(token, farmer_id, expires_at) VALUES (?, ?, ?)", (token, farmer_id, expiry.isoformat()))
    return token


def farmer_for_phone(phone_number: str) -> dict[str, Any] | None:
    """Return an existing farmer profile for a verified Indian mobile number."""
    normalized_phone = normalize_phone(phone_number)
    with _connection() as connection:
        row = connection.execute("SELECT * FROM farmers WHERE phone_number=?", (normalized_phone,)).fetchone()
    return dict(row) if row else None


def active_farmers_by_state() -> dict[str, int]:
    """Count unique farmers with at least one unexpired signed-in session by state."""
    with _connection() as connection:
        rows = connection.execute(
            """SELECT f.state, COUNT(DISTINCT f.id) AS farmer_count
            FROM farmers f JOIN sessions s ON s.farmer_id=f.id
            WHERE s.expires_at>?
            GROUP BY f.state""",
            (now().isoformat(),),
        ).fetchall()
    return {str(row["state"]): int(row["farmer_count"]) for row in rows}


def farmer_for_token(token: str) -> dict[str, Any] | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT f.* FROM sessions s JOIN farmers f ON f.id=s.farmer_id WHERE s.token=? AND s.expires_at>?",
            (token, now().isoformat()),
        ).fetchone()
    return dict(row) if row else None


def save_sample(farmer_id: str, filename: str, content_type: str, contents: bytes) -> tuple[str, Path]:
    sample_id = secrets.token_urlsafe(16)
    suffix = Path(filename).suffix.lower() or ".jpg"
    image_path = UPLOAD_DIR / f"{sample_id}{suffix}"
    image_path.write_bytes(contents)
    with _connection() as connection:
        connection.execute(
            "INSERT INTO samples(id, farmer_id, image_path, original_filename, content_type, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sample_id, farmer_id, str(image_path), filename, content_type, now().isoformat()),
        )
    return sample_id, image_path


def add_prediction(sample_id: str, prediction_json: str) -> None:
    with _connection() as connection:
        connection.execute("UPDATE samples SET prediction_json=? WHERE id=?", (prediction_json, sample_id))


def add_lab_result(sample_id: str, farmer_id: str, values: dict[str, float]) -> None:
    with _connection() as connection:
        record = connection.execute("SELECT id FROM samples WHERE id=? AND farmer_id=?", (sample_id, farmer_id)).fetchone()
        if not record:
            raise ValueError("Soil sample was not found for this farmer.")
        connection.execute(
            """UPDATE samples SET nitrogen_kg_ha=?, phosphorus_kg_ha=?, potassium_kg_ha=?,
            moisture_percent=?, lab_recorded_at=? WHERE id=?""",
            (values["nitrogen_kg_ha"], values["phosphorus_kg_ha"], values["potassium_kg_ha"], values.get("moisture_percent"), now().isoformat(), sample_id),
        )


def _export_labeled_dataset() -> int:
    """Export only uploaded images that have certified numeric NPK labels."""
    labels_path = TRAINING_DIR / "labels.csv"
    with _connection() as connection:
        rows = connection.execute(
            "SELECT id, image_path, nitrogen_kg_ha, phosphorus_kg_ha, potassium_kg_ha FROM samples "
            "WHERE nitrogen_kg_ha IS NOT NULL AND phosphorus_kg_ha IS NOT NULL AND potassium_kg_ha IS NOT NULL"
        ).fetchall()
    fields = ["sample_id", "image_path", "nitrogen_kg_ha", "phosphorus_kg_ha", "potassium_kg_ha"]
    with labels_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({"sample_id": row["id"], **{field: row[field] for field in fields[1:]}})
    return len(rows)


def retrain_if_ready() -> dict[str, Any]:
    count = _export_labeled_dataset()
    if count < MIN_LABELED_SAMPLES:
        return {"status": "waiting_for_lab_labels", "labeled_samples": count, "minimum_required": MIN_LABELED_SAMPLES}
    metrics = train(TRAINING_DIR / "labels.csv", MODEL_PATH)
    return {"status": "retrained", "labeled_samples": count, "metrics": metrics}


def model_status() -> dict[str, Any]:
    count = _export_labeled_dataset()
    return {"model_available": MODEL_PATH.exists(), "labeled_samples": count, "minimum_required": MIN_LABELED_SAMPLES}
