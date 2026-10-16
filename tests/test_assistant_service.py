"""Safety and data-source regression tests; run with PYTHONPATH=src python -m unittest discover -s tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from soil_npk.api import AssistantQuestion, _assistant_calls, _check_assistant_rate, kisan_mitra_advice
from soil_npk.assistant_service import (
    _chat_generation_config,
    _knowledge_for,
    _redact_private_text,
    answer_farmer_question,
    scheme_directory,
    weather_for_farmer,
)


FARMER = {"id": "test", "district": "Bhiwani", "state": "Haryana"}


class AssistantServiceTests(unittest.TestCase):
    def test_gemini_three_reserves_room_for_visible_reply(self) -> None:
        config = _chat_generation_config("gemini-3.6-flash")
        self.assertEqual(config["thinkingConfig"]["thinkingLevel"], "minimal")
        self.assertGreaterEqual(config["maxOutputTokens"], 768)

    def test_sensitive_numbers_are_removed(self) -> None:
        result = _redact_private_text("Call 9876543210, Aadhaar 1234 5678 9012 and PAN ABCDE1234F")
        for secret in ("9876543210", "1234 5678 9012", "ABCDE1234F"):
            self.assertNotIn(secret, result)

    def test_crop_guides_exist(self) -> None:
        for crop in ("wheat", "rice", "cotton", "sugarcane", "tomato", "onion", "soybean"):
            self.assertIsNotNone(_knowledge_for(crop))

    def test_all_scheme_links_are_official(self) -> None:
        schemes = scheme_directory()
        self.assertEqual(len(schemes), 10)
        self.assertTrue(all(item["link"].startswith("https://") for item in schemes))

    def test_missing_key_gets_nonempty_safe_fallback(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            reply = answer_farmer_question("How much pesticide should I spray on wheat?", FARMER, "English", "general")
        self.assertEqual(reply["mode"], "fallback")
        self.assertIn("KVK", reply["answer"])

    def test_mandi_request_never_fabricates_a_price(self) -> None:
        reply = answer_farmer_question("What is today's mandi price for cotton?", FARMER, "English", "general")
        self.assertEqual(reply["mode"], "source_link")
        self.assertIn("AGMARKNET", reply["answer"])
        self.assertEqual(reply["sources"][0]["url"], "https://agmarknet.gov.in/")

    def test_weather_is_five_days_and_india_filtered(self) -> None:
        place = Mock()
        place.json.return_value = {"results": [{"name": "Bhiwani", "admin1": "Haryana", "latitude": 28.8, "longitude": 76.1}]}
        forecast = Mock()
        forecast.json.return_value = {"daily": {"time": ["2026-10-02", "2026-10-03"]}}
        with patch("soil_npk.assistant_service.requests.get", side_effect=[place, forecast]) as get:
            result = weather_for_farmer("Bhiwani", "Haryana")
        self.assertEqual(get.call_args_list[0].kwargs["params"]["countryCode"], "IN")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["forecast_days"], 5)
        self.assertEqual(result["days"][0]["date"], "2026-10-02")

    def test_weather_text_without_consent_does_not_call_provider(self) -> None:
        with patch("soil_npk.assistant_service.requests.get") as get:
            reply = answer_farmer_question("Will it rain tomorrow?", FARMER, "English", "general")
        self.assertEqual(reply["mode"], "consent_needed")
        get.assert_not_called()

    def test_unverified_chemical_rate_is_blocked(self) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Use pesticide 5 ml/litre."}]}}]}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("soil_npk.assistant_service.requests.post", return_value=response):
            result = answer_farmer_question("Pests on cotton, help", FARMER, "English", "general")
        self.assertEqual(result["mode"], "fallback")
        self.assertNotIn("5 ml/litre", result["answer"])

    def test_weather_requires_explicit_consent(self) -> None:
        with self.assertRaises(HTTPException) as context:
            kisan_mitra_advice(AssistantQuestion(question="Will it rain?", request_type="crop_weather"), FARMER)
        self.assertEqual(context.exception.status_code, 422)

    def test_chat_rate_limit_is_30_per_ten_minutes(self) -> None:
        _assistant_calls.pop("unit-test-farmer", None)
        with patch("soil_npk.api.time.monotonic", return_value=1000.0):
            for _ in range(30):
                _check_assistant_rate("unit-test-farmer")
            with self.assertRaises(HTTPException) as context:
                _check_assistant_rate("unit-test-farmer")
        self.assertEqual(context.exception.status_code, 429)
        _assistant_calls.pop("unit-test-farmer", None)


if __name__ == "__main__":
    unittest.main()
