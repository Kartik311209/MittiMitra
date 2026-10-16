"""Privacy-conscious Gemini AI and weather helpers for the MittiMitra assistant."""

from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any
import wave

import requests


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
RETIRED_GEMINI_MODELS = {"gemini-2.5-flash", "models/gemini-2.5-flash"}
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
KISAN_CALL_CENTRE = "1800-180-1551"
KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"
SCHEMES_PATH = Path(__file__).resolve().parents[2] / "data" / "schemes.json"


def scheme_directory(query: str = "") -> list[dict[str, Any]]:
    """Curated official links; never infer personal eligibility from a profile."""
    if not SCHEMES_PATH.is_file():
        return []
    entries = json.loads(SCHEMES_PATH.read_text(encoding="utf-8"))
    needle = query.strip().casefold()
    return [entry for entry in entries if not needle or needle in f"{entry['name']} {entry['benefit']} {entry['id']}".casefold()]


def _redact_private_text(value: str) -> str:
    """Do not forward common Indian identifiers or phone numbers to an AI provider."""
    value = re.sub(r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)", "[mobile number removed]", value)
    value = re.sub(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)", "[ID number removed]", value)
    value = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "[ID number removed]", value, flags=re.IGNORECASE)
    return value


def _knowledge_for(question: str) -> tuple[str, str] | None:
    crops = {
        "wheat": ("wheat", "गेहूं", "गेहूँ", "gahu"),
        "rice": ("rice", "paddy", "धान", "चावल"),
        "cotton": ("cotton", "कपास"),
        "sugarcane": ("sugarcane", "गन्ना"),
        "tomato": ("tomato", "टमाटर"),
        "onion": ("onion", "प्याज", "प्याज़"),
        "soybean": ("soybean", "सोयाबीन"),
    }
    lower = question.casefold()
    for crop, aliases in crops.items():
        if any(alias in lower for alias in aliases):
            file = KB_DIR / f"{crop}.md"
            if file.is_file():
                return file.read_text(encoding="utf-8"), crop
    return None


def _fallback(language: str, question: str, weather: dict[str, Any] | None) -> str:
    """Give a safe next step, never a made-up dose, weather figure or price."""
    lower = question.casefold()
    if any(word in lower for word in ("helpline", "help line", "call centre", "call center", "हेल्पलाइन", "कॉल सेंटर")):
        return ("Call the Kisan Call Centre at 1800-180-1551 for farming guidance."
                if language == "English" else "खेती की सलाह के लिए किसान कॉल सेंटर 1800-180-1551 पर फोन करें।")
    if any(word in lower for word in ("mandi", "भाव", "bhaav", "price", "rate")):
        if language == "English":
            return "I cannot verify today's mandi price here. Check the dated price for your crop and market on AGMARKNET, then confirm with the local mandi before selling."
        return "आज का मंडी भाव यहाँ पक्का नहीं देख पा रहा हूँ। AGMARKNET पर अपनी फसल और मंडी का तारीख वाला भाव देखें, फिर बेचने से पहले स्थानीय मंडी से पुष्टि करें।"
    if any(word in lower for word in ("scheme", "yojana", "योजना", "subsidy")):
        if language == "English":
            return "Check the current scheme, eligibility and application deadline on the official MyScheme portal. Do not share Aadhaar or bank details in this chat; ask your local agriculture office for help."
        return "योजना की मौजूदा पात्रता और अंतिम तारीख आधिकारिक MyScheme पोर्टल पर देखें। आधार या बैंक जानकारी इस चैट में न लिखें; मदद के लिए कृषि कार्यालय जाएँ।"
    if language == "English":
        if weather:
            return "Check the dated 5-day forecast below before irrigating or spraying. Weather can change, so confirm locally before a costly decision. For crop-specific advice, call 1800-180-1551."
        if any(word in lower for word in ("buffalo", "cow", "milk", "भैंस", "गाय", "दूध")):
            return "Give clean water and a balanced ration; change feed gradually. If the animal is ill or milk drops suddenly, contact a veterinarian. For farm guidance, call 1800-180-1551."
        if knowledge := _knowledge_for(question):
            return f"For {knowledge[1]}, inspect the crop and confirm the problem before any spray. Check soil moisture before irrigating, and ask your local KVK for this season's sowing window or treatment. Call 1800-180-1551 if you need help now."
        return "I cannot verify a specific answer right now. Tell me the crop, district and problem, or call the Kisan Call Centre at 1800-180-1551. Confirm any chemical dose with your local KVK."
    if weather:
        return "सिंचाई या छिड़काव से पहले नीचे दिया 5 दिन का मौसम देखें। मौसम बदल सकता है; बड़ा खर्च करने से पहले स्थानीय कृषि अधिकारी से पुष्टि करें। फसल सलाह के लिए 1800-180-1551 पर कॉल करें।"
    if any(word in lower for word in ("buffalo", "cow", "milk", "भैंस", "गाय", "दूध")):
        return "पशु को साफ पानी और संतुलित चारा दें; चारा धीरे-धीरे बदलें। पशु बीमार हो या दूध अचानक घटे तो पशु चिकित्सक से बात करें। खेती की सलाह के लिए 1800-180-1551 पर कॉल करें।"
    if _knowledge_for(question):
        return "फसल को ध्यान से देखें और समस्या की पहचान किए बिना छिड़काव न करें। सिंचाई से पहले मिट्टी की नमी जाँचें; इस मौसम की बुवाई या उपचार की पुष्टि स्थानीय KVK से करें। मदद के लिए 1800-180-1551 पर कॉल करें।"
    return "अभी पक्की जानकारी नहीं मिल सकी। फसल, ज़िला और समस्या बताएं या किसान कॉल सेंटर 1800-180-1551 पर बात करें। दवा की मात्रा स्थानीय KVK से पुष्ट करें।"


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


def _chat_generation_config(model: str) -> dict[str, Any]:
    """Reserve enough output tokens for Gemini 3 thinking and the short reply."""
    config: dict[str, Any] = {"maxOutputTokens": 1024}
    if model.startswith("gemini-3."):
        level = "minimal" if model.startswith(("gemini-3.5-", "gemini-3.6-")) else "low"
        config["thinkingConfig"] = {"thinkingLevel": level}
    return config


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
            params={"name": f"{district}, {state}", "count": 5, "countryCode": "IN", "language": "en", "format": "json"},
            timeout=6,
        )
        place.raise_for_status()
        matches = place.json().get("results", [])
        if not matches:
            raise AssistantProviderError("Forecast location could not be found for the registered district.")
        match = next((item for item in matches if item.get("admin1", "").casefold() == state.casefold()), matches[0])
        forecast = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": match["latitude"], "longitude": match["longitude"],
                "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration",
                "timezone": "Asia/Kolkata", "forecast_days": 5,
            },
            timeout=6,
        )
        forecast.raise_for_status()
        daily = forecast.json().get("daily", {})
        return {
            "location": f"{match.get('name', district)}, {match.get('admin1', state)}, India",
            "days": [
                {
                    "date": day,
                    "min_c": daily.get("temperature_2m_min", [None] * 5)[index],
                    "max_c": daily.get("temperature_2m_max", [None] * 5)[index],
                    "rain_mm": daily.get("precipitation_sum", [None] * 5)[index],
                    "rain_probability": daily.get("precipitation_probability_max", [None] * 5)[index],
                    "et0_mm": daily.get("et0_fao_evapotranspiration", [None] * 5)[index],
                }
                for index, day in enumerate(daily.get("time", []))
            ],
            "source": "Open-Meteo forecast",
            "source_url": "https://open-meteo.com/",
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
        try:
            weather = weather_for_farmer(str(farmer["district"]), str(farmer["state"]))
        except AssistantProviderError:
            weather = None
        if weather is None:
            answer = ("The live forecast is unavailable. Do not make a spray or irrigation decision from a guessed forecast; check the local weather service or call 1800-180-1551."
                      if language == "English" else "अभी लाइव मौसम नहीं मिल रहा है। अनुमान लगाकर छिड़काव या सिंचाई तय न करें; स्थानीय मौसम सेवा देखें या 1800-180-1551 पर बात करें।")
            return {"answer": answer, "weather": None, "sources": [], "mode": "fallback"}

    if request_type != "crop_weather" and any(word in question.casefold() for word in ("weather", "forecast", "rain", "मौसम", "बारिश", "baarish", "mausam")):
        answer = ("Choose the weather topic and allow district-level lookup to see a dated forecast."
                  if language == "English" else "तारीख वाला मौसम देखने के लिए मौसम विषय चुनें और ज़िला-स्तर की जानकारी इस्तेमाल करने की अनुमति दें।")
        return {"answer": answer, "weather": None, "sources": [], "mode": "consent_needed"}

    knowledge = _knowledge_for(question)
    sources = ([{"name": "Open-Meteo", "url": weather["source_url"], "date": weather["days"][0]["date"]}] if weather and weather["days"] else [])
    if knowledge:
        sources.append({"name": "MittiMitra crop guide (general)", "url": "", "date": ""})
    lower_question = question.casefold()
    if any(word in lower_question for word in ("mandi", "भाव", "bhaav", "price", "rate")):
        return {"answer": _fallback(language, question, weather), "weather": weather,
                "sources": [{"name": "AGMARKNET", "url": "https://agmarknet.gov.in/", "date": ""}], "mode": "source_link"}
    if any(word in lower_question for word in ("scheme", "yojana", "योजना", "subsidy")):
        return {"answer": _fallback(language, question, weather), "weather": weather,
                "sources": [{"name": "MyScheme", "url": "https://www.myscheme.gov.in/", "date": ""}], "mode": "source_link"}
    instructions = f"""You are Mitarr, a helpful agricultural advisor for Indian farmers.
Reply in {language}, using the same language as the farmer when clear. Default Hindi. Use simple spoken language.
Maximum 4 short sentences or 3-5 short bullets, under 90 words. Lead with an action. Ask one clarifying question if needed.
NEVER invent pesticide, insecticide, fertiliser doses, brand names or chemical combinations. If an exact dose is not in the supplied knowledge, defer to local KVK or Kisan Call Centre 1800-180-1551.
Prefer IPM/cultural remedies first. Never give medical advice for humans or livestock; refer to a doctor or vet.
For crop failure, health, loans, insurance, land, or other high-stakes decisions ask for confirmation with the local Agriculture Officer or KVK.
Use only facts in the supplied crop guide or weather. Never invent a mandi price, weather figure, scheme eligibility or crop yield. If unknown, say so and offer the helpline.
Weather is a short forecast, not seasonal climate. This is not a lab report or guaranteed prediction.
Never ask for, repeat or expose phone numbers, Aadhaar, bank details or land documents.
Crop guide: {knowledge[0][:3500] if knowledge else 'No verified crop-specific guide supplied.'}
Weather data (only when requested): {weather if weather else 'Unavailable or not requested.'}
"""
    model = _gemini_model()
    body = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": _redact_private_text(question.strip())}]}],
        "generationConfig": _chat_generation_config(model),
        "store": False,
    }
    try:
        response = requests.post(f"{GEMINI_API_BASE_URL}/models/{model}:generateContent", headers=_headers(), json=body, timeout=8)
        response.raise_for_status()
        answer = _response_text(response.json())
        # The supplied crop guides intentionally contain no chemical doses.
        # Block numerical application rates even if a provider ignores the prompt.
        if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:ml|millilitre|मि\.ली\.|gram|grams|gm|g|kg|किलो|ग्राम)\s*(?:/|per|प्रति)\s*(?:l|litre|liter|लीटर|acre|एकड़|hectare|हेक्टेयर)", answer, re.IGNORECASE):
            raise AssistantProviderError("Unverified chemical rate blocked.")
        if len(answer.split()) > 90:
            answer = " ".join(answer.split()[:90]).rstrip(".,;:") + "…"
        return {"answer": answer, "weather": weather, "sources": sources, "mode": "ai"}
    except (AssistantConfigurationError, AssistantProviderError, requests.RequestException, ValueError):
        return {"answer": _fallback(language, question, weather), "weather": weather, "sources": sources, "mode": "fallback"}


def transcribe_farmer_voice(audio: bytes, filename: str, content_type: str, language: str) -> str:
    if not audio or len(audio) > 15 * 1024 * 1024:
        raise ValueError("Voice recording must be between 1 byte and 15 MB.")
    _ = filename
    supported_languages = {
        "Hindi", "Hinglish", "English", "Assamese", "Bengali", "Bodo", "Dogri",
        "Gujarati", "Kannada", "Kashmiri", "Konkani", "Maithili", "Malayalam",
        "Manipuri", "Marathi", "Nepali", "Odia", "Punjabi", "Sanskrit", "Santali",
        "Sindhi", "Tamil", "Telugu", "Urdu",
    }
    language_hint = "Hindi/Hinglish" if language == "Hinglish" else language if language in supported_languages else "Hindi/Hinglish"
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
