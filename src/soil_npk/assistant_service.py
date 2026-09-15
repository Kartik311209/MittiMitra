"""Privacy-conscious Gemini AI and weather helpers for the MittiMitra assistant."""

from __future__ import annotations

import base64
import io
import os
from typing import Any
import wave

import requests


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
RETIRED_GEMINI_MODELS = {"gemini-2.5-flash", "models/gemini-2.5-flash"}
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class AssistantConfigurationError(RuntimeError):
    """Raised when the optional Gemini integration has not been configured."""


class AssistantProviderError(RuntimeError):
    """Raised when an external AI or weather provider cannot fulfil a request."""


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise AssistantConfigurationError(
            "Kisan Mitra AI is not configured yet. Add GEMINI_API_KEY to .env and restart Docker."
        )
    return key


def _headers() -> dict[str, str]:
    return {"x-goog-api-key": _api_key(), "Content-Type": "application/json"}


def _gemini_model(setting: str = "GEMINI_MODEL") -> str:
    """Keep existing .env files working after Gemini retires a model."""
    model = os.getenv(setting, "gemini-3.6-flash").strip().removeprefix("models/")
    return "gemini-3.6-flash" if model in RETIRED_GEMINI_MODELS else model


def _provider_message(response: requests.Response) -> str:
    try:
        detail = response.json().get("error", {}).get("message") or response.json().get("detail")
    except ValueError:
        detail = None
    return str(detail or "The AI service could not complete the request.")


def weather_for_farmer(district: str, state: str) -> dict[str, Any]:
    """Fetch a short forecast only after the farmer explicitly requests it."""
    try:
        place = requests.get(
            OPEN_METEO_GEOCODING_URL,
            params={"name": f"{district}, {state}, India", "count": 1, "language": "en", "format": "json"},
            timeout=12,
        )
        place.raise_for_status()
        matches = place.json().get("results", [])
        if not matches:
            raise AssistantProviderError("Forecast location could not be found for the registered district.")
        match = matches[0]
        forecast = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": match["latitude"], "longitude": match["longitude"],
                "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration",
                "timezone": "auto", "forecast_days": 7,
            },
            timeout=12,
        )
        forecast.raise_for_status()
        daily = forecast.json().get("daily", {})
        return {
            "location": f"{match.get('name', district)}, {match.get('admin1', state)}, India",
            "days": [
                {
                    "date": day,
                    "min_c": daily.get("temperature_2m_min", [None] * 7)[index],
                    "max_c": daily.get("temperature_2m_max", [None] * 7)[index],
                    "rain_mm": daily.get("precipitation_sum", [None] * 7)[index],
                    "rain_probability": daily.get("precipitation_probability_max", [None] * 7)[index],
                    "et0_mm": daily.get("et0_fao_evapotranspiration", [None] * 7)[index],
                }
                for index, day in enumerate(daily.get("time", []))
            ],
            "source": "Open-Meteo forecast",
        }
    except requests.RequestException as error:
        raise AssistantProviderError("Weather forecast is temporarily unavailable. Please try again shortly.") from error


def _response_text(payload: dict[str, Any]) -> str:
    for candidate in payload.get("candidates", []):
        for content in candidate.get("content", {}).get("parts", []):
            if content.get("text"):
                return str(content["text"]).strip()
    raise AssistantProviderError("The AI service returned an empty answer. Please try again.")


def answer_farmer_question(
    question: str,
    farmer: dict[str, object],
    language: str,
    request_type: str,
) -> dict[str, object]:
    """Generate a bounded advisory without sending a farmer's name or phone number."""
    weather: dict[str, Any] | None = None
    if request_type == "crop_weather":
        weather = weather_for_farmer(str(farmer["district"]), str(farmer["state"]))

    context = {
        "registered_location": {
            "state": farmer["state"], "district": farmer["district"], "tehsil": farmer["city"],
            "village": farmer["village"],
        },
        "land_holding": {"size": farmer["land_size"], "unit": farmer["land_unit"]},
        "weather_forecast": weather,
    }
    instructions = f"""You are Kisan Mitra, a helpful agricultural assistant for Indian farmers.
Reply in {language}. Use plain, short farmer-friendly language and headings/bullets.
You can advise on crops, weather-aware planning, soil care and buffalo/cattle feed, but do not claim to be a veterinarian, agronomist, government authority, or guarantee profit/yield.
For animal illness, pregnancy, sudden drop in milk, fever, poisoning, bloat, injury, or a calf emergency, advise immediate contact with a qualified veterinarian.
For milk yield, give only general ration principles, clean water, gradual feed changes and a prompt to confirm ration with a local veterinarian/animal nutritionist; never prescribe drugs or exact medicinal treatment.
For crop choice, clearly distinguish the 7-day forecast from seasonal climate. Explain assumptions and suggest local KVK/agriculture department confirmation before spending money.
Never ask for, repeat, or expose phone numbers, Aadhaar numbers, bank information, or precise land documents.
The following is the farmer's non-identifying context and any explicitly requested forecast: {context}
"""
    model = _gemini_model()
    body = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": question.strip()}]}],
        "generationConfig": {"maxOutputTokens": 700},
        "store": False,
    }
    try:
        response = requests.post(f"{GEMINI_API_BASE_URL}/models/{model}:generateContent", headers=_headers(), json=body, timeout=45)
    except requests.RequestException as error:
        raise AssistantProviderError("Kisan Mitra AI is temporarily unavailable. Please try again.") from error
    if not response.ok:
        raise AssistantProviderError(_provider_message(response))
    return {"answer": _response_text(response.json()), "weather": weather}


def transcribe_farmer_voice(audio: bytes, filename: str, content_type: str, language: str) -> str:
    if not audio or len(audio) > 15 * 1024 * 1024:
        raise ValueError("Voice recording must be between 1 byte and 15 MB.")
    _ = filename
    language_hint = {"Hindi": "Hindi", "Hinglish": "Hindi/Hinglish", "English": "English"}.get(language, "Hindi/Hinglish")
    model = _gemini_model("GEMINI_TRANSCRIPTION_MODEL")
    body = {
        "contents": [{"role": "user", "parts": [
            {"text": f"Transcribe this farmer's {language_hint} voice question accurately. Return only the transcript, with no explanation."},
            {"inlineData": {"mimeType": content_type or "audio/wav", "data": base64.b64encode(audio).decode("ascii")}},
        ]}],
        "generationConfig": {"maxOutputTokens": 500},
        "store": False,
    }
    try:
        response = requests.post(
            f"{GEMINI_API_BASE_URL}/models/{model}:generateContent", headers=_headers(), json=body,
            timeout=60,
        )
    except requests.RequestException as error:
        raise AssistantProviderError("Voice transcription is temporarily unavailable. Please try again.") from error
    if not response.ok:
        raise AssistantProviderError(_provider_message(response))
    transcript = _response_text(response.json())
    if not transcript:
        raise AssistantProviderError("The recording could not be understood. Please record again in a quieter place.")
    return transcript


def synthesize_assistant_voice(text: str) -> str:
    """Generate a WAV reply using Gemini's free-tier TTS preview model."""
    body = {
        "model": os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        "input": text[:3500],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": os.getenv("GEMINI_TTS_VOICE", "Kore")}]} ,
    }
    try:
        response = requests.post(f"{GEMINI_API_BASE_URL}/interactions", headers=_headers(), json=body, timeout=60)
    except requests.RequestException as error:
        raise AssistantProviderError("AI voice reply is temporarily unavailable. Please try again.") from error
    if not response.ok:
        raise AssistantProviderError(_provider_message(response))
    payload = response.json()
    audio = payload.get("outputAudio") or payload.get("output_audio") or {}
    raw_audio = str(audio.get("data") or "")
    if not raw_audio:
        raise AssistantProviderError("The AI voice service returned no audio. Please try again.")
    # Gemini TTS returns 24kHz mono 16-bit PCM. Add a WAV container for browsers.
    wav_output = io.BytesIO()
    with wave.open(wav_output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(base64.b64decode(raw_audio))
    return base64.b64encode(wav_output.getvalue()).decode("ascii")
