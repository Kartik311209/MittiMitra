"""Run with: python -m streamlit run dashboard.py."""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
import requests

from soil_npk.state_portals import STATE_EXTRA_RESOURCES, STATE_PORTALS


API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(page_title="MittiMitra | Soil Intelligence", page_icon="🌱", layout="wide")


# The component keeps the India outline as a real vector map.  It intentionally
# uses the local Highcharts map dataset instead of rendering a pasted screenshot.
INDIA_ACTIVITY_MAP = st.components.v2.component(
    "mittimitra_india_activity_map",
    html="""<div class="map-shell"><div class="map-gloss"></div><div class="map-topline"><span class="map-dot"></span><span id="map-status">Loading India map…</span><span class="map-scale"><i></i><span id="map-legend">Lower GVA → Higher GVA</span></span></div><div id="india-activity-map"></div></div>""",
    css="""
        .map-shell { position: relative; isolation: isolate; box-sizing: border-box; min-height: 650px; overflow: hidden; border: 1px solid rgba(88, 144, 101, .28); border-radius: 20px; background: linear-gradient(145deg, #fcfff9 0%, #edf8ee 48%, #fff8e9 100%); box-shadow: 0 18px 42px rgba(33, 89, 53, .16), inset 0 1px 0 rgba(255,255,255,.92); }
        .map-gloss { position: absolute; z-index: 0; inset: 0; pointer-events: none; background: radial-gradient(ellipse at 18% -22%, rgba(255,255,255,.95) 0 25%, transparent 53%), linear-gradient(116deg, transparent 18%, rgba(255,255,255,.42) 32%, transparent 46%); }
        .map-topline { position: relative; z-index: 1; display: flex; align-items: center; gap: .45rem; padding: .82rem 1rem .52rem; color: #285c3b; font: 800 .76rem/1.2 system-ui, sans-serif; letter-spacing: .035em; text-transform: uppercase; }
        .map-dot { width: .58rem; height: .58rem; border-radius: 50%; background: #2f9d61; box-shadow: 0 0 0 4px rgba(47,157,97,.14); }
        .map-scale { margin-left: auto; display: inline-flex; align-items: center; gap: .42rem; color: #55715d; font-size: .66rem; letter-spacing: .01em; text-transform: none; white-space: nowrap; }
        .map-scale i { display: inline-block; width: 4.9rem; height: .5rem; border: 1px solid rgba(36,95,58,.2); border-radius: 999px; background: linear-gradient(90deg, #e2f4e7, #a8dfbd 38%, #55b978 70%, #126b45); box-shadow: inset 0 1px 1px rgba(255,255,255,.78); }
        #india-activity-map { position: relative; z-index: 1; width: 100%; height: 600px; min-height: 600px; }
        @media (max-width: 700px) { .map-shell { min-height: 510px; } #india-activity-map { height: 465px; min-height: 465px; } }
    """,
    js="""
        const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character]));
        const loadScript = (source, id) => new Promise((resolve, reject) => {
            const existing = document.getElementById(id);
            if (existing) {
                if (window.Highcharts && (id !== "mittimitra-highmaps" || window.Highcharts.mapChart)) resolve();
                else existing.addEventListener("load", resolve, { once: true });
                return;
            }
            const script = document.createElement("script");
            script.id = id;
            script.src = source;
            script.async = true;
            script.onload = resolve;
            script.onerror = () => reject(new Error(`Could not load ${source}`));
            document.head.appendChild(script);
        });

        export default async function(component) {
            const { data, parentElement } = component;
            const target = parentElement.querySelector("#india-activity-map");
            const status = parentElement.querySelector("#map-status");
            if (!target || !data) return;

            const assetBase = `${window.location.protocol}//${window.location.hostname}:8000/assets/maps`;
            try {
                await loadScript(`${assetBase}/highmaps.js`, "mittimitra-highmaps");
                await loadScript(`${assetBase}/in-all-disputed.js`, "mittimitra-india-disputed-map");
                const H = window.Highcharts;
                const topology = H && H.maps && H.maps["countries/in/custom/in-all-disputed"];
                if (!H || !topology) throw new Error("India vector boundary data was unavailable");

                const normalise = (value) => String(value || "").toLowerCase().replace(/islands|union territory|nct of|and /g, "").replace(/[^a-z]/g, "");
                const aliases = {
                    "dadranagarhavelidamandiu": ["damandiu", "dadranagarhaveli", "dadaraandnagarhavelli"],
                    "delhi": ["nctofdelhi", "delhi"],
                    "jammuandkashmir": ["jammuandkashmir"],
                };
                const abbreviations = {
                    "Andaman and Nicobar Islands":"AN", "Andhra Pradesh":"AP", "Arunachal Pradesh":"AR", "Assam":"AS", "Bihar":"BR", "Chhattisgarh":"CG", "Dadra and Nagar Haveli and Daman and Diu":"DN", "Delhi":"DL", "Goa":"GA", "Gujarat":"GJ", "Haryana":"HR", "Himachal Pradesh":"HP", "Jammu and Kashmir":"JK", "Jharkhand":"JH", "Karnataka":"KA", "Kerala":"KL", "Ladakh":"LA", "Lakshadweep":"LD", "Madhya Pradesh":"MP", "Maharashtra":"MH", "Manipur":"MN", "Meghalaya":"ML", "Mizoram":"MZ", "Nagaland":"NL", "Odisha":"OD", "Puducherry":"PY", "Punjab":"PB", "Rajasthan":"RJ", "Sikkim":"SK", "Tamil Nadu":"TN", "Telangana":"TS", "Tripura":"TR", "Uttar Pradesh":"UP", "Uttarakhand":"UK", "West Bengal":"WB"
                };
                // Chandigarh is intentionally omitted: at this scale it is covered by Punjab/Haryana.
                const shapes = H.geojson(topology).filter((shape) => normalise(shape.properties && shape.properties["hc-key"]) !== "chandigarh");
                const mapData = [];
                for (const item of (data.items || [])) {
                    const rawKey = normalise(item.state);
                    const possibleKeys = [rawKey, ...(aliases[rawKey] || [])];
                    const matches = shapes.filter((shape) => possibleKeys.includes(normalise(shape.properties && shape.properties["hc-key"])) || possibleKeys.includes(normalise(shape.properties && shape.properties.name)));
                    for (const shape of matches) {
                        mapData.push({
                            mapKey: shape.properties["hc-key"],
                            state: item.state,
                            abbr: abbreviations[item.state] || "",
                            active: Number(item.active_farmers || 0),
                            beneficiaries: Number(item.pm_kisan_beneficiaries || 0),
                            crops: item.key_crops || "—",
                            soils: item.common_soils || "—",
                            gva: item.agriculture_gsva_share_percent,
                            value: typeof item.agriculture_gsva_share_percent === "number" ? item.agriculture_gsva_share_percent : null,
                        });
                    }
                }

                if (target.__mittiMap) target.__mittiMap.destroy();
                target.__mittiMap = H.mapChart(target, {
                    chart: { map: topology, backgroundColor: "transparent", animation: false, spacing: [0, 0, 0, 0], style: { fontFamily: "system-ui, sans-serif" } },
                    title: { text: null }, credits: { enabled: false }, mapNavigation: { enabled: false },
                    mapView: { padding: [10, 12, 12, 12] },
                    tooltip: {
                        useHTML: true, borderWidth: 0, borderRadius: 10, shadow: { color: "rgba(62,47,18,.24)", opacity: .24, width: 9, offsetX: 0, offsetY: 3 }, backgroundColor: "#243727", padding: 12,
                        formatter: function () {
                            const point = this.point;
                            if (!point.state) return `<b style="color:#fff">${escapeHtml(point.name || "India")}</b>`;
                            const gva = point.gva === null || point.gva === undefined ? "—" : `${escapeHtml(point.gva)}%`;
                            return `<div style="min-width:205px;color:#e9f4e8;font:13px/1.4 system-ui,sans-serif"><b style="font-size:15px;color:#fff">${escapeHtml(point.state)}</b><br><span>Active farmers: <b>${escapeHtml(point.active.toLocaleString("en-IN"))}</b></span><br><span>PM-KISAN: <b>${escapeHtml(point.beneficiaries.toLocaleString("en-IN"))}</b></span><br><span>Agriculture GVA: <b>${gva}</b></span><br><span>Key crops: ${escapeHtml(point.crops)}</span><br><span>Soils: ${escapeHtml(point.soils)}</span></div>`;
                        }
                    },
                    colorAxis: {
                        min: 0, max: 42,
                        stops: [[0, "#e2f4e7"], [.35, "#a8dfbd"], [.7, "#55b978"], [1, "#126b45"]]
                    },
                    series: [{
                        data: mapData, mapData: shapes, joinBy: ["hc-key", "mapKey"], name: "India",
                        borderColor: "rgba(255,255,255,.88)", borderWidth: 1, nullColor: "#f8fbf6",
                        states: { hover: { color: "#f6bd4b", borderColor: "#895c16", borderWidth: 1.35 } },
                        dataLabels: {
                            enabled: true, allowOverlap: false, padding: 0, useHTML: true,
                            formatter: function () {
                                if (!this.point.abbr) return "";
                                const textColor = Number(this.point.value || 0) >= 25 ? "#ffffff" : "#225538";
                                return `<span style="color:${textColor};font-size:8px;font-weight:800;text-shadow:0 1px 1px rgba(255,255,255,.42)">${escapeHtml(this.point.abbr)}</span>`;
                            }
                        }
                    }]
                });
                status.textContent = data.status || "Interactive India farmer map";
            } catch (error) {
                status.textContent = "India map could not load. Please refresh once.";
                target.innerHTML = '<div style="padding:3rem 1.5rem;color:#765b28;font:600 1rem system-ui,sans-serif">Interactive India map is temporarily unavailable.</div>';
            }
            return () => { if (target.__mittiMap) { target.__mittiMap.destroy(); target.__mittiMap = null; } };
        }
    """,
    isolate_styles=True,
)


LANGUAGE_LABELS = {
    "Hindi": "🌐 हिंदी", "Hinglish": "🌐 Hinglish", "English": "🌐 English",
    "Assamese": "🌐 অসমীয়া", "Bengali": "🌐 বাংলা", "Bodo": "🌐 बड़ो", "Dogri": "🌐 डोगरी",
    "Gujarati": "🌐 ગુજરાતી", "Kannada": "🌐 ಕನ್ನಡ", "Kashmiri": "🌐 کٲشُر", "Konkani": "🌐 कोंकणी",
    "Maithili": "🌐 मैथिली", "Malayalam": "🌐 മലയാളം", "Manipuri": "🌐 মৈতৈলোন্", "Marathi": "🌐 मराठी",
    "Nepali": "🌐 नेपाली", "Odia": "🌐 ଓଡ଼ିଆ", "Punjabi": "🌐 ਪੰਜਾਬੀ", "Sanskrit": "🌐 संस्कृत",
    "Santali": "🌐 ᱥᱟᱱᱛᱟᱲᱤ", "Sindhi": "🌐 سنڌي", "Tamil": "🌐 தமிழ்", "Telugu": "🌐 తెలుగు", "Urdu": "🌐 اردو",
}
LANGUAGE_CODES = {
    "Assamese": "as", "Bengali": "bn", "Bodo": "brx", "Dogri": "doi", "Gujarati": "gu", "Kannada": "kn",
    "Kashmiri": "ks", "Konkani": "gom", "Maithili": "mai", "Malayalam": "ml", "Manipuri": "mni", "Marathi": "mr",
    "Nepali": "ne", "Odia": "or", "Punjabi": "pa", "Sanskrit": "sa", "Santali": "sat", "Sindhi": "sd",
    "Tamil": "ta", "Telugu": "te", "Urdu": "ur",
}
OFFICIAL_SCHEME_POSTERS = (
    ("₹", "PM-KISAN", "Income support and beneficiary-status services for eligible farmer families.", "https://pmkisan.gov.in/"),
    ("🛡", "PMFBY", "Crop-insurance enrolment, premium and application-status services.", "https://pmfby.gov.in/"),
    ("◉", "Soil Health Card", "Official soil-testing and nutrient-advice information for farmers.", "https://soilhealth.dac.gov.in/"),
    ("🌾", "Natural Farming", "Official updates on natural-farming clusters and farmer support.", "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2244625&lang=1&reg=1"),
    ("▣", "Farmer Registry", "Official information on verified farmer-record initiatives.", "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251120700401.pdf"),
    ("↗", "MyScheme", "Search official government schemes and check their details.", "https://www.myscheme.gov.in/"),
)
SCHEME_POSTER_COPY = {
    "Hindi": (
        "पात्र किसान परिवारों के लिए सहायता और लाभार्थी स्थिति।",
        "फसल बीमा, प्रीमियम और आवेदन की जानकारी।",
        "मिट्टी जाँच और पोषक सलाह की सरकारी जानकारी।",
        "प्राकृतिक खेती और किसान सहायता के आधिकारिक अपडेट।",
        "सत्यापित किसान रिकॉर्ड की आधिकारिक जानकारी।",
        "सरकारी योजनाएँ खोजें और उनका विवरण देखें।",
    ),
    "Hinglish": (
        "Eligible farmer families ke liye support aur beneficiary status.",
        "Crop insurance, premium aur application ki jaankari.",
        "Soil test aur nutrient advice ki sarkari jaankari.",
        "Natural farming aur farmer support ke official updates.",
        "Verified farmer record initiative ki official jaankari.",
        "Sarkari schemes search karein aur details dekhein.",
    ),
    "English": tuple(item[2] for item in OFFICIAL_SCHEME_POSTERS),
}
SCHEME_POSTER_STATUS = {
    "Hindi": (
        ("active", "सक्रिय • पात्रता जाँचें"),
        ("seasonal", "राज्य/मौसम के अनुसार"),
        ("active", "सेवा उपलब्ध"),
        ("info", "केवल जानकारी"),
        ("rollout", "राज्य के अनुसार जारी"),
        ("active", "लाइव योजना डायरेक्टरी"),
    ),
    "Hinglish": (
        ("active", "Active • eligibility check karein"),
        ("seasonal", "State/season ke hisaab se"),
        ("active", "Service available"),
        ("info", "Sirf information"),
        ("rollout", "State-wise rollout"),
        ("active", "Live scheme directory"),
    ),
    "English": (
        ("active", "Active • check eligibility"),
        ("seasonal", "Depends on state/season"),
        ("active", "Service available"),
        ("info", "Information only"),
        ("rollout", "State-wise rollout"),
        ("active", "Live scheme directory"),
    ),
}
REGISTRATION_TEXT = {
    "Hindi": {
        "intro": "अपनी जानकारी भरें; मोबाइल पर आए OTP से डैशबोर्ड खुलेगा।", "name": "किसान का नाम *", "name_hint": "जैसे: रमेश कुमार",
        "age": "उम्र *", "land_unit": "ज़मीन की इकाई *", "land_size": "कितनी ज़मीन है? *",
        "location": "स्थान चुनें: राज्य → ज़िला/शहर → तहसील → गाँव", "state": "राज्य *", "state_choose": "राज्य चुनें",
        "district": "ज़िला / शहर *", "district_choose": "ज़िला / शहर चुनें", "tehsil": "तहसील *", "tehsil_choose": "तहसील चुनें",
        "village": "गाँव *", "village_choose": "गाँव चुनें", "phone": "मोबाइल नंबर *", "phone_hint": "10 अंकों का मोबाइल नंबर",
        "directory_missing": "इस राज्य की आधिकारिक स्थान-सूची अभी लोड नहीं हुई है। LGD डेटा जोड़ने के बाद ज़िला, तहसील और गाँव की A–Z सूची दिखेगी।",
        "opt_in": "सरकारी योजना और लाभ की SMS सूचनाएँ चाहिए", "small_farm": "छोटी जोत वाले किसानों के लिए योजनाओं की सूचना भी भेजें",
        "scheme_note": "सूचनाएँ केवल आधिकारिक स्रोत से होंगी; पात्रता सरकार के नियम तय करेंगे।", "send": "OTP बनाएं",
        "required": "कृपया सभी जानकारी और स्थान चयन पूरा करें।", "sent": "OTP तैयार है। नीचे कोड डालकर लॉगिन करें।",
        "screen_otp": "डेमो OTP (SMS नहीं भेजा गया): {otp}",
        "otp": "6 अंकों का OTP", "otp_hint": "OTP डालें", "verify": "OTP सत्यापित करके डैशबोर्ड खोलें", "edit": "जानकारी बदलें",
        "existing_farmer": "पहले से पंजीकृत किसान? केवल OTP से लॉगिन करें", "returning_intro": "मोबाइल नंबर डालें। आपकी पहले वाली जानकारी सुरक्षित रहेगी; दोबारा नहीं भरनी पड़ेगी।",
        "returning_send": "लॉगिन OTP बनाएं", "returning_verify": "OTP सत्यापित करके लॉगिन करें", "back_to_registration": "नई जानकारी भरें", "new_registration": "नया किसान पंजीकरण", "back_to_login": "केवल लॉगिन पर वापस जाएँ",
        "units": ["एकड़ (Acre)", "हेक्टेयर (Hectare)", "बीघा (Bigha)", "कनाल (Kanal)", "मरला (Marla)", "कट्ठा / कठ्ठा (Katha)", "बिस्वा (Biswa)", "बिस्वांसी (Biswansi)", "गुंठा / गुंटा (Guntha)", "सेंट (Cent)", "डेसिमल (Decimal)", "ग्राउंड (Ground)", "वर्ग मीटर (Square metre)"],
    },
    "Hinglish": {
        "intro": "Apni jaankari bharein; mobile par aaye OTP se dashboard khulega.", "name": "Kisaan ka naam *", "name_hint": "Jaise: Ramesh Kumar",
        "age": "Umar *", "land_unit": "Zameen ki unit *", "land_size": "Kitni zameen hai? *",
        "location": "Location selection: Rajya → Jila/City → Tehsil → Gaon", "state": "Rajya *", "state_choose": "Rajya chunein",
        "district": "Jila / City *", "district_choose": "Jila / City chunein", "tehsil": "Tehsil *", "tehsil_choose": "Tehsil chunein",
        "village": "Gaon *", "village_choose": "Gaon chunein", "phone": "Mobile number *", "phone_hint": "10-digit mobile number",
        "directory_missing": "Is Rajya ki official location list abhi load nahi hui. LGD data add hote hi Jila, Tehsil aur Gaon ki A–Z list dikhegi.",
        "opt_in": "Government scheme aur benefits ki SMS updates chahiye", "small_farm": "Chhoti joat ke farmers ke liye schemes ki updates bhi bhejein",
        "scheme_note": "Sirf official-source updates bheje jayenge; eligibility sarkari rules se decide hogi.", "send": "OTP banayein",
        "required": "Kripya saari details aur location selection poora karein.", "sent": "OTP ready hai. Neeche code daalkar login karein.",
        "screen_otp": "Demo OTP (SMS nahi bheja gaya): {otp}",
        "otp": "6-digit OTP", "otp_hint": "OTP daalein", "verify": "OTP verify karke dashboard kholein", "edit": "Details badlein",
        "existing_farmer": "Pehle se registered farmer? Sirf OTP se login karein", "returning_intro": "Mobile number daalein. Aapki purani details safe rahengi; dobara nahi bharni padegi.",
        "returning_send": "Login OTP banayein", "returning_verify": "OTP verify karke login karein", "back_to_registration": "Nayi details bharein", "new_registration": "Naya farmer registration", "back_to_login": "Sirf login par wapas jaayein",
        "units": ["Acre", "Hectare", "Bigha", "Kanal", "Marla", "Katha / Kattha", "Biswa", "Biswansi", "Guntha / Gunta", "Cent", "Decimal", "Ground", "Square metre"],
    },
    "English": {
        "intro": "Enter your details; the dashboard opens after mobile OTP verification.", "name": "Farmer's name *", "name_hint": "For example: Ramesh Kumar",
        "age": "Age *", "land_unit": "Land unit *", "land_size": "Land area *",
        "location": "Select location: State → District/City → Tehsil → Village", "state": "State *", "state_choose": "Select state",
        "district": "District / City *", "district_choose": "Select district / city", "tehsil": "Tehsil *", "tehsil_choose": "Select tehsil",
        "village": "Village *", "village_choose": "Select village", "phone": "Mobile number *", "phone_hint": "10-digit mobile number",
        "directory_missing": "The official location directory for this state has not been loaded yet. Add LGD data to show the A–Z district, tehsil and village lists.",
        "opt_in": "Send me SMS updates on government schemes and benefits", "small_farm": "Also send updates relevant to small landholders",
        "scheme_note": "Updates use official sources only; the government decides eligibility under each scheme.", "send": "Generate OTP",
        "required": "Complete all required details and location selections.", "sent": "Your OTP is ready. Enter it below to log in.",
        "screen_otp": "Demo OTP (no SMS was sent): {otp}",
        "otp": "6-digit OTP", "otp_hint": "Enter OTP", "verify": "Verify OTP and open dashboard", "edit": "Edit details",
        "existing_farmer": "Already registered? Log in with OTP only", "returning_intro": "Enter your mobile number. Your saved details stay secure; you do not need to enter them again.",
        "returning_send": "Generate login OTP", "returning_verify": "Verify OTP and log in", "back_to_registration": "Register new details", "new_registration": "New farmer registration", "back_to_login": "Back to login only",
        "units": ["Acre", "Hectare", "Bigha", "Kanal", "Marla", "Katha / Kattha", "Biswa", "Biswansi", "Guntha / Gunta", "Cent", "Decimal", "Ground", "Square metre"],
    },
}
INSTANT_RESULT_TEXT = {
    "Hindi": {
        "waiting": "इसी अपलोड की गई फोटो का परिणाम यहीं दिखेगा।",
        "ready": "इसी फोटो का अनुमान तैयार है।",
        "detail": "नीचे विस्तृत सुझाव और लैब-रिपोर्ट विकल्प भी है।",
    },
    "Hinglish": {
        "waiting": "Isi uploaded photo ka result yahin dikhega.",
        "ready": "Prediction isi photo ke liye ready hai.",
        "detail": "Neeche detailed guidance aur lab-result option bhi hai.",
    },
    "English": {
        "waiting": "The result for this uploaded photo will appear here.",
        "ready": "The prediction for this photo is ready.",
        "detail": "Detailed guidance and the lab-result option are below.",
    },
}
TRANSLATIONS = {
    "Hindi": {
        "top_bar": "मृदा NPK विश्लेषण • किसान सहायता", "prototype": "स्वतंत्र प्रोटोटाइप",
        "language": "भाषा", "hero_kicker": "बेहतर फैसलों के लिए मिट्टी की जानकारी",
        "hero_title": "अपनी मिट्टी को समझें।<br>फसल को बेहतर बनाएं।",
        "hero_copy": "मिट्टी की फोटो अपलोड करके NPK, अनुमानित नमी और फसल के लिए उपयोगी संकेत देखें—एक आसान, किसान-अनुकूल प्रक्रिया में।",
        "hero_chip": "🌱 सिंथेटिक AI प्रोटोटाइप • लैब जाँच की सलाह दी जाती है",
        "access": "किसान प्रवेश", "start": "शुरू करें", "login_copy": "डेमो एक्सेस से अपना मिट्टी विश्लेषण डैशबोर्ड खोलें।",
        "name": "नाम", "name_placeholder": "अपना नाम लिखें", "access_key": "एक्सेस कुंजी", "access_placeholder": "डेमो के लिए कुछ भी लिखें",
        "open_dashboard": "डैशबोर्ड खोलें", "name_error": "कृपया अपना नाम लिखें।",
        "tools": "किसान टूल", "photo_title": "फोटो से विश्लेषण", "photo_copy": "मिट्टी की फोटो से NPK और नमी का प्रोटोटाइप अनुमान।",
        "water_title": "पानी व फसल संकेत", "water_copy": "नमी के स्तर के आधार पर सावधानीपूर्ण फसल सुझाव।",
        "state_title": "राज्य-वार सहायता", "state_copy": "चुने हुए राज्य के कृषि संसाधन एक जगह देखें।",
        "updates": "भारत सरकार / किसान अपडेट", "updates_heading": "हाल की राष्ट्रीय किसान पहल", "official_update": "आधिकारिक अपडेट", "read_update": "आधिकारिक जानकारी पढ़ें ↗",
        "sign_out": "साइन आउट", "hello": "नमस्ते", "soil_intelligence": "मिट्टी की जानकारी",
        "dashboard_title": "अपनी मिट्टी को समझें।<br><span style='color:#1f9254'>विश्वास से योजना बनाएं।</span>",
        "dashboard_copy": "NPK का प्रोटोटाइप अनुमान, पोषक-स्तर और सावधानीपूर्ण अगला कदम पाने के लिए मिट्टी की फोटो अपलोड करें।",
        "camera_badge": "AI सहायता • कैमरा इनपुट", "prototype_note": "प्रोटोटाइप मॉडल नोट", "prototype_copy": "यह मॉडल पूरी तरह सिंथेटिक डेटा पर प्रशिक्षित है। इसका अनुमान तैयार किए गए दृश्य पैटर्न और मिट्टी के औसत मान-सीमा पर आधारित है—यह <strong>लैब रिपोर्ट नहीं है</strong>। NPK मान और उर्वरक की मात्रा प्रमाणित मृदा प्रयोगशाला से जाँचें।",
        "analyse": "01 / नमूने का विश्लेषण", "upload": "मिट्टी की फोटो अपलोड करें", "preview": "मिट्टी के नमूने का पूर्वावलोकन", "run": "NPK अनुमान चलाएँ", "input_hint": "बेहतर फोटो: साफ छवि, प्राकृतिक रोशनी, पत्ते या पत्थर नहीं।", "model_missing": "मॉडल नहीं मिला। पहले डेटा जनरेट और मॉडल ट्रेन करें।", "reading": "मिट्टी के दृश्य संकेत पढ़े जा रहे हैं...",
        "profile": "02 / अनुमानित पोषक प्रोफ़ाइल", "nitrogen": "नाइट्रोजन · N", "phosphorus": "फॉस्फोरस · P", "potassium": "पोटैशियम · K", "moisture": "मिट्टी की नमी", "next_step": "अनुशंसित अगला कदम", "crop_match": "प्रोटोटाइप फसल मिलान", "crop_hint": "मुख्यतः अनुमानित नमी-स्तर पर आधारित; स्थानीय मौसम, मौसम-चक्र और कृषि सलाह से उपयुक्तता की पुष्टि करें।", "method": "यह अनुमान कैसे निकाला गया?", "method_note": "सिंथेटिक छवियों में इन दृश्य संकेतों को NPK और नमी लेबल से जोड़ा गया है। असली मिट्टी में इस संबंध की पुष्टि के लिए लैब रिपोर्ट आवश्यक है।",
        "state_services": "राज्य किसान सेवाएँ", "portals": "के लिए उपयोगी पोर्टल", "change_state": "राज्य बदलें", "select_state": "राज्य चुनें", "official_resource": "आधिकारिक संसाधन", "department": "आधिकारिक कृषि विभाग", "farmer_resource": "आधिकारिक किसान संसाधन", "open_portal": "पोर्टल खोलें ↗", "external_note": "बाहरी लिंक सुविधा के लिए दिए गए हैं। MittiMitra एक स्वतंत्र प्रोटोटाइप है, सरकारी सेवा नहीं।",
    },
    "Hinglish": {
        "top_bar": "SOIL NPK ANALYSIS • FARMER SUPPORT", "prototype": "Independent prototype", "language": "Language", "hero_kicker": "Behtar faislon ke liye mitti ki jaankari", "hero_title": "Apni mitti ko samjho.<br>Fasal ko behtar banao.", "hero_copy": "Soil photo upload karke NPK, estimated moisture aur fasal ke useful signals dekhiye—ek simple, farmer-friendly process mein.", "hero_chip": "🌱 Synthetic AI prototype • Lab test ki salah di jaati hai", "access": "Farmer access", "start": "Shuru karein", "login_copy": "Demo access se apna soil analysis dashboard kholiye.", "name": "Naam", "name_placeholder": "Apna naam likhiye", "access_key": "Access key", "access_placeholder": "Demo ke liye kuch bhi likhiye", "open_dashboard": "Dashboard kholein", "name_error": "Kripya apna naam likhiye.", "tools": "Farmer tools", "photo_title": "Photo-based analysis", "photo_copy": "Soil photo se NPK aur moisture ka prototype estimate.", "water_title": "Paani aur fasal signals", "water_copy": "Moisture level ke base par cautious crop suggestions.", "state_title": "State-wise support", "state_copy": "Selected state ke agriculture resources ek jagah dekhiye.", "updates": "Government of India / farmer updates", "updates_heading": "Recent nationwide farmer initiatives", "official_update": "Official update", "read_update": "Official update padhein ↗", "sign_out": "Sign out", "hello": "Namaste", "soil_intelligence": "soil intelligence", "dashboard_title": "Apni mitti ko samjho.<br><span style='color:#1f9254'>Confidence se plan banao.</span>", "dashboard_copy": "Prototype NPK estimate, nutrient status aur cautious next step ke liye soil photo upload karein.", "camera_badge": "AI-ASSISTED • CAMERA INPUT", "prototype_note": "Prototype model note", "prototype_copy": "Yeh model poori tarah synthetic data par trained hai. Iska estimate generated visual patterns aur soil ke average-value ranges par based hai—yeh <strong>lab result nahi hai</strong>. NPK values aur fertilizer dosage certified soil lab se confirm karein.", "analyse": "01 / sample analyse karein", "upload": "Soil photo upload karein", "preview": "Soil sample preview", "run": "NPK estimate chalayen", "input_hint": "Best photo: clear image, natural daylight, leaves ya stones nahi.", "model_missing": "Model nahi mila. Pehle data generate aur model train karein.", "reading": "Soil ke visual signals padhe ja rahe hain...", "profile": "02 / estimated nutrient profile", "nitrogen": "Nitrogen · N", "phosphorus": "Phosphorus · P", "potassium": "Potassium · K", "moisture": "Soil moisture", "next_step": "Recommended next step", "crop_match": "Prototype crop match", "crop_hint": "Mainly estimated moisture band par based; local season, climate aur crop advisories se suitability confirm karein.", "method": "Yeh estimate kaise nikla?", "method_note": "Synthetic images mein in visual signals ko NPK aur moisture labels se joda gaya hai. Real soil ke liye lab report zaroori hai.", "state_services": "State farmer services", "portals": "ke useful portals", "change_state": "State badlein", "select_state": "State chunein", "official_resource": "Official resource", "department": "Official agriculture department", "farmer_resource": "Official farmer resource", "open_portal": "Portal kholein ↗", "external_note": "External links convenience ke liye hain. TerraNPK ek independent prototype hai, official government service nahi.",
    },
    "English": {
        "top_bar": "SOIL NPK ANALYSIS • FARMER SUPPORT", "prototype": "Independent prototype", "language": "Language", "hero_kicker": "Soil intelligence for better decisions", "hero_title": "Understand your soil.<br>Grow better crops.", "hero_copy": "Upload a soil photo to view NPK, estimated moisture and practical crop signals in a simple, farmer-friendly workflow.", "hero_chip": "🌱 Synthetic AI prototype • Laboratory verification recommended", "access": "Farmer access", "start": "Get started", "login_copy": "Use demo access to open your soil analysis dashboard.", "name": "Name", "name_placeholder": "Enter your name", "access_key": "Access key", "access_placeholder": "Enter anything for the demo", "open_dashboard": "Open dashboard", "name_error": "Please enter your name.", "tools": "Farmer tools", "photo_title": "Photo-based analysis", "photo_copy": "Prototype NPK and moisture estimate from a soil image.", "water_title": "Water & crop signals", "water_copy": "Cautious crop suggestions based on the moisture band.", "state_title": "State-wise support", "state_copy": "Find agriculture resources for your selected state.", "updates": "Government of India / farmer updates", "updates_heading": "Recent nationwide farmer initiatives", "official_update": "Official update", "read_update": "Read official update ↗", "sign_out": "Sign out", "hello": "Hello", "soil_intelligence": "soil intelligence", "dashboard_title": "Understand your soil.<br><span style='color:#1f9254'>Plan with confidence.</span>", "dashboard_copy": "Upload a soil image to get a prototype NPK estimate, nutrient status and a cautious next step.", "camera_badge": "AI-ASSISTED • CAMERA INPUT", "prototype_note": "Prototype model note", "prototype_copy": "This model is trained fully on synthetic data. Its estimate is based on generated visual patterns and average soil-value ranges—it is <strong>not a laboratory result</strong>. Confirm NPK values and fertilizer dosage through a certified soil laboratory.", "analyse": "01 / analyse a sample", "upload": "Upload soil image", "preview": "Soil sample preview", "run": "Run NPK estimate", "input_hint": "Best input: a sharp image in natural daylight, with no leaves or stones.", "model_missing": "Model not found. Generate data and train the model first.", "reading": "Reading visual soil signals...", "profile": "02 / estimated nutrient profile", "nitrogen": "Nitrogen · N", "phosphorus": "Phosphorus · P", "potassium": "Potassium · K", "moisture": "Soil moisture", "next_step": "Recommended next step", "crop_match": "Prototype crop match", "crop_hint": "Based primarily on the estimated moisture band; confirm suitability with local season, climate and crop advisories.", "method": "How was this estimate calculated?", "method_note": "Synthetic images deliberately connect these visual signals to NPK and moisture labels. In real soil, laboratory reports are required to validate this relationship.", "state_services": "State farmer services", "portals": "useful portals", "change_state": "Change state", "select_state": "Select state", "official_resource": "Official resource", "department": "Official agriculture department", "farmer_resource": "Official farmer resource", "open_portal": "Open portal ↗", "external_note": "External links are provided for convenience. TerraNPK is an independent prototype, not an official government service.",
    },
}


def selected_language() -> str:
    return str(st.session_state.get("language", "Hindi"))


def language_mode() -> str:
    """Use manual translations where available; other Indian languages use English source text."""
    selection = selected_language()
    return selection if selection in {"Hindi", "Hinglish", "English"} else "English"


@st.cache_data(ttl=60 * 60 * 24 * 14, show_spinner=False)
def translate_static_text(text: str, target: str) -> str:
    """Translate fixed UI copy only; farmer records and user-entered text never leave the app."""
    try:
        response = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"en|{target}"},
            timeout=8,
        )
        response.raise_for_status()
        translated = str(response.json().get("responseData", {}).get("translatedText", ""))
        return translated or text
    except (requests.RequestException, ValueError, IndexError, TypeError):
        return text


def translated_ui_text(text: str) -> str:
    target = LANGUAGE_CODES.get(selected_language())
    return translate_static_text(text, target) if target else text


def tr(key: str) -> str:
    source = TRANSLATIONS[language_mode()][key].replace("TerraNPK", "MittiMitra")
    return translated_ui_text(source)


def registration_text(key: str) -> str | list[str]:
    source = REGISTRATION_TEXT[language_mode()][key]
    if isinstance(source, list):
        return [translated_ui_text(item) for item in source]
    return translated_ui_text(source)


def instant_result_text(key: str) -> str:
    return translated_ui_text(INSTANT_RESULT_TEXT[language_mode()][key])


def api_call(method: str, path: str, **kwargs: object) -> tuple[dict[str, object] | None, str | None]:
    """Call the persistent FastAPI backend and return a user-friendly error."""
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", timeout=30, **kwargs)
        if response.ok:
            return response.json(), None
        detail = response.json().get("detail", response.text)
        return None, str(detail)
    except requests.RequestException:
        return None, "Backend se connection nahi ho paaya. Docker services ya FastAPI server chalu kijiye."


def location_options(path: str, **params: str) -> list[str]:
    response, _ = api_call("GET", path, params=params)
    if not response:
        return []
    return [str(item) for item in response.get("items", [])]


def localized_status(status: str) -> str:
    labels = {
        "Hindi": {"Low": "कम", "Medium": "मध्यम", "High": "अधिक", "Dry": "सूखी", "Moist": "नम", "Balanced": "संतुलित", "Not estimated": "अनुमान उपलब्ध नहीं"},
        "Hinglish": {"Low": "Kam", "Medium": "Madhyam", "High": "Adhik", "Dry": "Sookhi", "Moist": "Nam", "Balanced": "Santulit", "Not estimated": "Estimate available nahi"},
        "English": {},
    }
    return labels[language_mode()].get(status, status)


def localized_actions(levels: dict[str, str]) -> list[str]:
    language = language_mode()
    if language == "Hindi":
        messages = {"nitrogen": "नाइट्रोजन कम प्रतीत हो रहा है: नाइट्रोजन स्रोत डालने से पहले लैब जाँच करें।", "phosphorus": "फॉस्फोरस कम प्रतीत हो रहा है: स्रोत और मात्रा के लिए स्थानीय कृषि सलाह लें।", "potassium": "पोटैशियम कम प्रतीत हो रहा है: पोटैशियम उपयोग बदलने से पहले मृदा लैब से पुष्टि करें।"}
        fallback = "इस प्रोटोटाइप अनुमान में कोई स्पष्ट कम पोषक संकेत नहीं है; मृदा लैब रिपोर्ट से पुष्टि करें।"
    elif language == "Hinglish":
        messages = {"nitrogen": "Nitrogen kam lag raha hai: nitrogen source dene se pehle lab test karein.", "phosphorus": "Phosphorus kam lag raha hai: source aur dose ke liye local agriculture guidance lein.", "potassium": "Potassium kam lag raha hai: application badalne se pehle soil lab se confirm karein."}
        fallback = "Is prototype estimate mein koi clear low-nutrient flag nahi hai; soil lab report se confirm karein."
    else:
        messages = {"nitrogen": "Nitrogen appears low: confirm through a lab test before applying a nitrogen source.", "phosphorus": "Phosphorus appears low: seek local agronomy guidance on a phosphorus source and dose.", "potassium": "Potassium appears low: confirm with a soil lab before changing potassium application."}
        fallback = "No obvious low nutrient flag in this prototype estimate; validate with a soil lab report."
    actions = [messages[nutrient] for nutrient, status in levels.items() if status == "Low"]
    return actions or [fallback]


def localized_crop(crop: str) -> str:
    crops = {
        "Hindi": {"Millet / bajra": "बाजरा", "Chickpea": "चना", "Mustard": "सरसों", "Paddy": "धान", "Fodder crops": "चारा फसलें", "Wheat": "गेहूँ", "Maize": "मक्का", "Groundnut": "मूंगफली"},
        "Hinglish": {"Wheat": "Gehoon", "Maize": "Makka", "Groundnut": "Moongfali", "Chickpea": "Chana", "Mustard": "Sarson", "Paddy": "Dhaan", "Fodder crops": "Chara faslein"},
        "English": {},
    }
    return crops[language_mode()].get(crop, crop)


def scheme_updates() -> tuple[tuple[str, str, str], ...]:
    urls = (
        "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2244625&lang=1&reg=1",
        "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2292460&lang=1&reg=48",
        "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251120700401.pdf",
    )
    summaries = {
        "Hindi": ("मार्च 2026 के अपडेट में प्राकृतिक खेती क्लस्टर, किसान नामांकन और सहायता प्रावधानों पर प्रकाश डाला गया है।", "केंद्रीय मंत्रिमंडल ने PM-KISAN को 2026–27 से 2030–31 तक जारी रखने की मंजूरी दी; पात्रता आधिकारिक नियमों से तय होती है।", "सत्यापित किसान रिकॉर्ड के माध्यम से पात्र किसान कल्याण लाभ तक पहुँच आसान बनाने की डिजिटल पहल।"),
        "Hinglish": ("March 2026 update mein natural-farming clusters, farmer enrolment aur support provisions ko highlight kiya gaya hai.", "Union Cabinet ne PM-KISAN ko 2026–27 se 2030–31 tak continue karne ki approval di; eligibility official scheme rules par depend karti hai.", "Verified farmer record ke through eligible welfare benefits tak access easy banane ki digital initiative."),
        "English": ("A March 2026 update on the mission highlighted natural-farming clusters, farmer enrolment and support provisions.", "The Union Cabinet approved continuation of PM-KISAN for 2026–27 to 2030–31; eligibility is determined by the official scheme rules.", "A digital initiative intended to simplify access to eligible farmer welfare benefits through a verified farmer record."),
    }[language_mode()]
    return (("National Mission on Natural Farming", summaries[0], urls[0]), ("PM-KISAN continuation", summaries[1], urls[1]), ("Farmer Registry", summaries[2], urls[2]))


def render_scheme_posters(side: str) -> None:
    """Fill the login-page side rails with official, compact scheme posters."""
    start = 0 if side == "left" else 3
    poster_slice = OFFICIAL_SCHEME_POSTERS[start:start + 3]
    language = language_mode()
    label = {"Hindi": "सरकारी योजना", "Hinglish": "Sarkari yojana", "English": "Government scheme"}[language]
    action = {"Hindi": "आधिकारिक जानकारी देखें ↗", "Hinglish": "Official jaankari dekhein ↗", "English": "View official details ↗"}[language]
    for index, (icon, title, _, url) in enumerate(poster_slice, start=start):
        summary = SCHEME_POSTER_COPY[language][index]
        status_kind, status = SCHEME_POSTER_STATUS[language][index]
        st.markdown(
            f"""<a class='scheme-poster scheme-poster-{(index % 3) + 1}' href='{escape(url, quote=True)}' target='_blank' rel='noopener noreferrer'>
            <span class='scheme-poster-label'>{label}</span><span class='scheme-poster-icon'>{escape(icon)}</span>
            <strong>{escape(title)}</strong><span class='scheme-poster-status status-{status_kind}'>{escape(status)}</span><span class='scheme-poster-copy'>{escape(summary)}</span>
            <span class='scheme-poster-action'>{action}</span></a>""",
            unsafe_allow_html=True,
        )


def render_language_control() -> None:
    title, language = st.columns([4.6, 1.25])
    with title:
        st.markdown(f"<div class='top-strip'>{tr('top_bar')}<span>{tr('prototype')}</span></div>", unsafe_allow_html=True)
    with language:
        st.selectbox(tr("language"), list(LANGUAGE_LABELS), format_func=LANGUAGE_LABELS.get, key="language", label_visibility="collapsed")


def render_live_farmer_banner() -> None:
    """Show published national updates before login; state updates after verified login."""
    state = str(st.session_state.get("farmer_state", "")).strip() or None
    response, error = api_call("GET", "/scheme-updates/active", params={"state": state} if state else {})
    updates = response.get("items", []) if response and not error else []
    if not isinstance(updates, list) or not updates:
        return
    language = language_mode()
    label, link_text = {"Hindi": ("आधिकारिक अपडेट", "आधिकारिक सूचना देखें ↗"), "Hinglish": ("Official update", "Official update dekhein ↗"), "English": ("Official update", "View official update ↗")}[language]
    content_items = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        deadline = f" • Deadline: {escape(str(update['deadline']))}" if update.get("deadline") else ""
        content_items.append(f"<strong>{escape(str(update.get('title', '')))}:</strong> {escape(str(update.get('summary', '')))}{deadline} <a href='{escape(str(update.get('official_url', '')), quote=True)}' target='_blank' rel='noopener noreferrer'>{link_text}</a>")
    if not content_items:
        return
    content = "&nbsp;&nbsp; • &nbsp;&nbsp;".join(content_items)
    st.markdown(
        f"""<section class='live-alert' aria-label='Live farmer update'>
        <div class='live-label'><span class='live-dot'></span>{label}</div>
        <div class='live-ticker'><div class='live-ticker-track'><div class='live-item'>{content}</div><div class='live-item' aria-hidden='true'>{content}</div></div></div>
        </section>""",
        unsafe_allow_html=True,
    )


def render_how_it_works(compact: bool = False) -> None:
    """A plain-language explanation of the prototype's actual decision path."""
    language = language_mode()
    if language == "Hindi":
        heading, subheading = "यह ऐप कैसे काम करता है?", "सिर्फ 3 आसान कदम"
        steps = (
            ("1", "📷", "मिट्टी की साफ फोटो लें", "दिन की रोशनी में सिर्फ मिट्टी की फोटो लें—पत्ते, पत्थर या हाथ न हों।"),
            ("2", "🔎", "AI फोटो के रंग और बनावट को देखता है", "AI फोटो में रंग और मिट्टी की सतह का पैटर्न पढ़कर अपने अभ्यास वाले सिंथेटिक उदाहरणों से तुलना करता है।"),
            ("3", "🌱", "सरल अनुमान और अगला कदम", "आपको NPK, नमी और फसल के संकेत मिलते हैं। उर्वरक की मात्रा तय करने से पहले लैब जाँच जरूरी है।"),
        )
        note_label, note = "ज़रूरी बात", "यह ऐप मिट्टी को स्कैन नहीं करता और न ही लैब रिपोर्ट बनाता है—यह सिर्फ फोटो के पैटर्न से शुरुआती अनुमान देता है।"
    elif language == "Hinglish":
        heading, subheading = "Yeh app kaise kaam karta hai?", "Sirf 3 simple steps"
        steps = (
            ("1", "📷", "Soil ki clear photo lein", "Natural daylight mein sirf soil ki photo lein—leaves, stones ya haath nahi hone chahiye."),
            ("2", "🔎", "AI colour aur texture dekhta hai", "AI photo ke rang aur mitti ke surface pattern ko apne synthetic practice examples se compare karta hai."),
            ("3", "🌱", "Simple estimate aur next step", "Aapko NPK, moisture aur crop signals milte hain. Fertilizer dose decide karne se pehle lab test zaroori hai."),
        )
        note_label, note = "Zaroori baat", "Yeh app soil ko scan nahi karta aur lab report nahi banata—yeh photo patterns se sirf initial estimate deta hai."
    else:
        heading, subheading = "How does this app work?", "Three simple steps"
        steps = (
            ("1", "📷", "Take a clear soil photo", "Use natural daylight and keep leaves, stones and hands out of the image."),
            ("2", "🔎", "AI checks colour and texture", "It compares the photo's colour and surface-pattern signals with synthetic practice examples."),
            ("3", "🌱", "Get a simple estimate and next step", "You receive NPK, moisture and crop signals. Confirm fertilizer doses through a lab test."),
        )
        note_label, note = "Important", "This app does not scan soil or create a laboratory report—it gives an initial estimate from photo patterns only."

    if not compact:
        st.markdown(f"<div class='eyebrow'>{subheading}</div><h3 class='how-heading'>{heading}</h3>", unsafe_allow_html=True)
    for column, (number, icon, title, copy) in zip(st.columns(3), steps):
        with column:
            st.markdown(f"<div class='step-card'><div class='step-number'>{number}</div><div class='step-icon'>{icon}</div><div class='step-title'>{title}</div><div class='step-copy'>{copy}</div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='help-note'><strong>{note_label}:</strong> {note}</div>", unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
        .stApp {color:#183126;background:radial-gradient(circle at 2% 0%,#d9f0d6 0,transparent 30%),radial-gradient(circle at 100% 12%,#d7e8ff 0,transparent 28%),#f8fbf5;font-family:'Manrope',sans-serif;}
        #MainMenu,footer,header {visibility:hidden;} .block-container {max-width:1780px;padding-top:1.05rem;padding-bottom:2rem;}
        .brand {font-size:1.3rem;font-weight:800;letter-spacing:-.7px;color:#183126;} .brand span {color:#1f9254;}
        .eyebrow {font:500 .68rem 'DM Mono',monospace;color:#4b9d63;letter-spacing:.12em;text-transform:uppercase;}
        .hero {padding:.7rem 0 1.2rem;} .hero h1 {font-size:clamp(2.2rem,4.6vw,4.2rem);line-height:1.04;letter-spacing:-3px;margin:.4rem 0 .65rem;color:#173124;} .hero p {max-width:680px;color:#5c7163;font-size:1rem;line-height:1.6;margin:0;}
        .badge {display:inline-block;margin-top:.8rem;padding:.32rem .7rem;border-radius:999px;background:#e5f5e7;color:#28733e;font:500 .7rem 'DM Mono',monospace;}
        .notice {padding:.85rem 1rem;border-radius:14px;border:1px solid #f0d791;border-left:4px solid #d6a022;background:#fff9e8;color:#705a20;font-size:.88rem;line-height:1.52;} .notice strong {color:#594817;}
        .scan-card,.portal-panel,.metric-card {background:rgba(255,255,255,.92);border:1px solid #e0e9df;box-shadow:0 12px 32px rgba(34,79,52,.08);border-radius:18px;}
        .scan-card {padding:1.05rem;} .portal-panel {padding:1rem;position:sticky;top:1rem;}
        .portal-name {font-weight:800;font-size:1.05rem;color:#1e412e;margin:.2rem 0 .35rem;} .portal-copy {font-size:.8rem;color:#657a6b;line-height:1.45;margin-bottom:.8rem;} .resource-card,.scheme-card {background:#fff;border:1px solid #e0e9df;border-radius:15px;padding:1rem;min-height:120px;box-shadow:0 8px 24px rgba(34,79,52,.06);} .scheme-card {min-height:145px;border-top:3px solid #70b97d;}
        .metric-card {padding:1rem;min-height:118px;} .metric-label {font:500 .68rem 'DM Mono',monospace;color:#748c7a;letter-spacing:.08em;text-transform:uppercase;} .metric-value {font-size:1.95rem;font-weight:800;line-height:1.1;margin:.35rem 0 .12rem;color:#173124;} .metric-sub {font-size:.8rem;color:#528063;}
        .login-shell {max-width:460px;margin:8vh auto 0;} div[data-testid="stForm"] {padding:1rem;border-radius:16px;background:rgba(255,255,255,.9);border:1px solid #e0e9df;box-shadow:0 14px 38px rgba(34,79,52,.1);}
        div[data-testid="stFileUploader"] {padding:.55rem;border:1px dashed #82b58d;border-radius:14px;background:#fbfef9;}
        .stButton>button,.stLinkButton>a {border:0;border-radius:10px;background:#1f9254;color:white;font-weight:700;padding:.55rem .9rem;} .stButton>button:hover,.stLinkButton>a:hover {background:#167644;color:white;border:0;}
        .stTextInput input,.stSelectbox input {border-radius:9px;background:#fff!important;color:#183126!important;border-color:#d5e1d5;} div[data-testid="stTextInput"] label,div[data-testid="stTextInput"] label p {color:#294e37!important;font-size:.82rem!important;font-weight:700!important;} .stCaption {color:#718175!important;}
        .top-strip {margin:-1.45rem 0 1.2rem;padding:.55rem 1rem;background:#267c45;color:#f7fff5;font-size:.78rem;font-weight:700;letter-spacing:.03em;border-radius:0 0 8px 8px;} .top-strip span {float:right;font-weight:500;}
        .live-alert {display:flex;align-items:center;gap:.7rem;min-height:46px;margin:-.5rem 0 1rem;border:1px solid #badabe;border-left:4px solid #e8a326;border-radius:12px;background:#fffdf4;box-shadow:0 7px 20px rgba(55,91,57,.07);overflow:hidden;} .live-label {align-self:stretch;display:flex;align-items:center;gap:.38rem;padding:0 .8rem;background:#1e6f3d;color:#fff;font-size:.76rem;font-weight:800;white-space:nowrap;} .live-dot {width:7px;height:7px;border-radius:50%;background:#ffd26a;box-shadow:0 0 0 4px rgba(255,210,106,.18);animation:pulse 1.5s ease-in-out infinite;} .live-ticker {flex:1;overflow:hidden;} .live-ticker-track {display:flex;width:max-content;animation:ticker-scroll 38s linear infinite;} .live-item {white-space:nowrap;padding-right:5rem;font-size:.84rem;color:#465c4d;line-height:1.45;} .live-item a {color:#187243;font-weight:800;text-decoration:none;border-bottom:1px solid #9bc9a6;} @keyframes ticker-scroll {to {transform:translateX(-50%);}} @keyframes pulse {50% {opacity:.45;transform:scale(.8);}} @media (prefers-reduced-motion:reduce) {.live-ticker-track,.live-dot {animation:none;}}
        .login-hero {min-height:590px;border-radius:22px;background-position:center;background-size:cover;position:relative;overflow:hidden;box-shadow:0 15px 34px rgba(37,91,54,.18);} .login-hero:before {content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(10,45,25,.86) 0%,rgba(10,45,25,.56) 48%,rgba(10,45,25,.08) 100%);} .hero-copy {position:relative;z-index:1;padding:1.8rem;color:#f6fff0;max-width:72%;}.hero-copy h1 {font-size:clamp(2rem,3.7vw,3.6rem);line-height:1.06;letter-spacing:-2px;margin:.5rem 0 .8rem;color:#fff;}.hero-copy p {color:#e0f1df;line-height:1.55;font-size:.96rem;}.hero-kicker {font:500 .7rem 'DM Mono',monospace;letter-spacing:.12em;color:#bdecb6;text-transform:uppercase;}.hero-chip {display:inline-block;margin-top:.55rem;padding:.4rem .7rem;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.28);border-radius:999px;font-size:.76rem;}
        .login-panel {padding:.25rem .1rem;}.login-panel h3 {margin:.35rem 0;color:#183126;} div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .login-panel) {min-height:490px;box-sizing:border-box;padding:.8rem .85rem .65rem;border:1px solid #d8e7d9;border-radius:20px;background:rgba(255,255,255,.92);box-shadow:0 16px 34px rgba(34,79,52,.10);} .service-card {background:#fff;border:1px solid #e0e9df;border-radius:16px;padding:1rem;min-height:114px;box-shadow:0 8px 24px rgba(34,79,52,.06);}.service-icon {font-size:1.55rem;display:inline-block;margin-bottom:.35rem;}.service-title {font-weight:800;color:#224936;margin:.1rem 0 .3rem;}.service-copy {font-size:.82rem;line-height:1.45;color:#657a6b;}
        .scheme-poster {position:relative;display:flex;min-height:178px;margin-bottom:.72rem;padding:1rem .88rem;overflow:hidden;flex-direction:column;border:1px solid rgba(39,106,61,.2);border-radius:18px;background:linear-gradient(145deg,#f9fff4,#dff2d9);box-shadow:0 12px 26px rgba(34,79,52,.10);color:#183126;text-decoration:none;transition:transform .16s ease,box-shadow .16s ease;}.scheme-poster:hover {transform:translateY(-3px);box-shadow:0 16px 30px rgba(34,79,52,.16);color:#183126;}.scheme-poster:after {content:'';position:absolute;right:-32px;bottom:-42px;width:112px;height:112px;border:20px solid rgba(46,136,68,.10);border-radius:50%;}.scheme-poster-2 {background:linear-gradient(145deg,#fffbed,#f7e4a4);}.scheme-poster-3 {background:linear-gradient(145deg,#edf8ff,#d8ebf9);}.scheme-poster-label {font:700 .57rem 'DM Mono',monospace;letter-spacing:.1em;color:#478455;text-transform:uppercase;}.scheme-poster-icon {margin:.35rem 0 .15rem;font-size:1.45rem;color:#1f9254;font-weight:800;}.scheme-poster strong {position:relative;z-index:1;font-size:1rem;line-height:1.18;color:#1d432b;}.scheme-poster-status {position:relative;z-index:1;display:inline-flex;align-self:flex-start;margin-top:.35rem;padding:.16rem .38rem;border-radius:999px;font:700 .55rem 'DM Mono',monospace;letter-spacing:.02em;}.status-active {background:#dff3df;color:#23763a;}.status-seasonal {background:#fff0c5;color:#8a6410;}.status-info,.status-rollout {background:#e8edf1;color:#58707c;}.scheme-poster-copy {position:relative;z-index:1;margin-top:.4rem;font-size:.7rem;line-height:1.42;color:#516c59;}.scheme-poster-action {position:relative;z-index:1;margin-top:auto;padding-top:.5rem;font-size:.68rem;font-weight:800;color:#197844;}
        @media (max-width:1100px) {.block-container {max-width:1180px;} .scheme-poster {min-height:145px;padding:.72rem;}.scheme-poster-copy {display:none;}.login-hero {min-height:560px;} div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .login-panel) {min-height:470px;padding:.7rem;}}
        .how-heading {margin:.25rem 0 .75rem;color:#1e412e;font-size:1.32rem;}.step-card {position:relative;height:100%;min-height:162px;padding:1rem 1rem .95rem;border:1px solid #dce9de;border-radius:16px;background:#fff;box-shadow:0 8px 22px rgba(34,79,52,.055);}.step-number {position:absolute;right:.8rem;top:.7rem;display:grid;place-items:center;width:23px;height:23px;border-radius:50%;background:#e7f5e8;color:#267c45;font:700 .72rem 'DM Mono',monospace;}.step-icon {font-size:1.7rem;margin:.05rem 0 .4rem;}.step-title {color:#214a32;font-weight:800;font-size:.95rem;line-height:1.35;max-width:85%;}.step-copy {margin-top:.38rem;color:#657a6b;font-size:.79rem;line-height:1.48;}.help-note {margin:.75rem 0 1.15rem;padding:.68rem .85rem;border-radius:10px;border:1px solid #efdca3;background:#fffaf0;color:#6d5b2e;font-size:.82rem;line-height:1.48;}
        .st-key-kisan_mitra_floating {position:fixed!important;z-index:1000;right:1.15rem;bottom:1.15rem;width:min(390px,calc(100vw - 2.3rem));padding:0!important;overflow:hidden;border:1px solid rgba(71,153,88,.35)!important;border-radius:22px!important;background:linear-gradient(145deg,rgba(255,255,255,.99),rgba(235,250,238,.98))!important;box-shadow:0 24px 62px rgba(19,70,38,.28),inset 0 1px 0 rgba(255,255,255,.95)!important;backdrop-filter:blur(18px);}.st-key-kisan_mitra_floating .ai-float-hero {margin:-1rem -1rem .15rem;padding:1rem 1.05rem .9rem;background:radial-gradient(circle at 88% -30%,rgba(251,214,112,.8),transparent 48%),linear-gradient(132deg,#123f2b,#1d8751 62%,#4db476);color:#fff;}.ai-float-title-row {display:flex;align-items:center;gap:.65rem;}.ai-float-avatar {display:grid;place-items:center;width:38px;height:38px;border-radius:14px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);font-size:1.25rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.22);}.ai-float-title {font-size:1rem;font-weight:800;line-height:1.1;}.ai-float-status {margin-top:.17rem;font-size:.66rem;color:#cef6d7;}.ai-float-status i {display:inline-block;width:6px;height:6px;margin-right:.26rem;border-radius:50%;background:#e5f77d;box-shadow:0 0 0 4px rgba(229,247,125,.15);}.ai-float-hero p {margin:.72rem 0 0;color:#e6f8eb;font-size:.76rem;line-height:1.42;}.st-key-kisan_mitra_floating .ai-chat-history {margin:.15rem 0 .35rem;padding:.1rem .25rem;border:1px solid #d8eadb;border-radius:14px;background:rgba(255,255,255,.62);}.st-key-kisan_mitra_floating div[data-testid="stChatMessage"] {padding:.28rem .12rem!important;gap:.38rem!important;}.st-key-kisan_mitra_floating div[data-testid="stTextArea"] textarea {min-height:60px!important;font-size:.82rem!important;}.st-key-kisan_mitra_floating .stButton>button {font-size:.79rem;padding:.43rem .58rem;}.st-key-kisan_mitra_floating [data-testid="stPills"] {margin-top:.1rem;}.st-key-lab_lease_area {padding:1rem;border:1px solid #dbeadf;border-radius:20px;background:linear-gradient(145deg,#ffffff,#f1fbf2);box-shadow:0 14px 32px rgba(34,79,52,.08);}.st-key-profile_corner {margin-left:auto;} @media (max-width:800px) {.st-key-kisan_mitra_floating {position:relative!important;right:auto;bottom:auto;width:stretch;margin-top:1rem;}.st-key-kisan_mitra_floating .ai-float-hero {margin:-1rem -1rem .25rem;}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    hero_path = ROOT / "assets" / "farmer-field-hero.png"
    if hero_path.exists():
        encoded = base64.b64encode(hero_path.read_bytes()).decode("ascii")
        st.markdown(f"<style>.login-hero {{background-image:url('data:image/png;base64,{encoded}');}}</style>", unsafe_allow_html=True)


def render_new_farmer_registration() -> None:
    """The full form is intentionally separate from the compact returning-login view."""
    if st.button(registration_text("back_to_login"), key="close_registration"):
        st.session_state.pop("show_registration", None)
        st.rerun()
    with st.container(height=385, border=False):
        full_name = st.text_input(registration_text("name"), placeholder=registration_text("name_hint"))
        first, second = st.columns(2)
        with first:
            age = st.number_input(registration_text("age"), min_value=14, max_value=120, value=25, step=1)
        with second:
            land_unit = st.selectbox(registration_text("land_unit"), registration_text("units"))
        land_size = st.number_input(registration_text("land_size"), min_value=0.1, max_value=100000.0, value=1.0, step=0.1)
        st.caption(registration_text("location"))
        states = [registration_text("state_choose")] + location_options("/locations/states")
        state = st.selectbox(registration_text("state"), states, key="registration_state")
        districts = location_options("/locations/districts", state=state) if state != states[0] else []
        district_options = [registration_text("district_choose")] + districts
        district = st.selectbox(registration_text("district"), district_options, key="registration_district", disabled=not districts)
        tehsils = location_options("/locations/tehsils", state=state, district=district) if district != district_options[0] else []
        tehsil_options = [registration_text("tehsil_choose")] + tehsils
        tehsil = st.selectbox(registration_text("tehsil"), tehsil_options, key="registration_tehsil", disabled=not tehsils)
        villages = location_options("/locations/villages", state=state, district=district, tehsil=tehsil) if tehsil != tehsil_options[0] else []
        village_options = [registration_text("village_choose")] + villages
        village = st.selectbox(registration_text("village"), village_options, key="registration_village", disabled=not villages)
        if state != states[0] and not districts:
            st.warning(registration_text("directory_missing"))
        phone_number = st.text_input(registration_text("phone"), placeholder=registration_text("phone_hint"))
        scheme_sms_opt_in = st.checkbox(registration_text("opt_in"), value=False)
        small_farm_updates = st.checkbox(registration_text("small_farm"), value=False, disabled=not scheme_sms_opt_in)
        st.caption(registration_text("scheme_note"))
        submitted = st.button(registration_text("send"), use_container_width=True, type="primary")
    if not submitted:
        return
    profile = {
        "full_name": full_name.strip(), "age": int(age), "land_size": float(land_size), "land_unit": land_unit,
        "village": village, "district": district, "tehsil": tehsil, "state": state, "phone_number": phone_number.strip(),
        "scheme_sms_opt_in": scheme_sms_opt_in, "small_farm_updates": small_farm_updates,
    }
    placeholders = {states[0], district_options[0], tehsil_options[0], village_options[0]}
    required_profile_fields = ("full_name", "village", "district", "tehsil", "state", "phone_number")
    if any(not profile[key] for key in required_profile_fields) or any(value in placeholders for value in profile.values() if isinstance(value, str)):
        st.error(registration_text("required"))
        return
    response, error = api_call("POST", "/auth/request-otp", json={"phone_number": profile["phone_number"]})
    if error:
        st.error(error)
    else:
        st.session_state.pending_profile = profile
        st.session_state.pending_otp = response.get("otp") if response else None
        st.session_state.login_step = "otp"
        st.rerun()


def login_screen() -> None:
    render_language_control()
    render_live_farmer_banner()
    left_posters, hero_column, login_column, right_posters = st.columns([.42, 1.6, .86, .42], gap="small")
    with left_posters:
        render_scheme_posters("left")
    with hero_column:
        st.markdown(f"""<section class="login-hero"><div class="hero-copy"><div class="hero-kicker">{tr('hero_kicker')}</div><h1>{tr('hero_title')}</h1><p>{tr('hero_copy')}</p><div class="hero-chip">{tr('hero_chip')}</div></div></section>""", unsafe_allow_html=True)
    with login_column:
        st.markdown(f"<div class='login-panel'><div class='brand'>Mitti<span>Mitra</span></div><div class='eyebrow'>{tr('access')}</div><h3>{tr('start')}</h3></div>", unsafe_allow_html=True)
        st.caption(registration_text("intro"))
        if st.button("Admin portal login", icon=":material/admin_panel_settings:", width="stretch", key="open_admin_portal"):
            st.session_state.admin_mode = True
            st.rerun()
        if st.session_state.get("login_step", "profile") == "profile":
            if not st.session_state.get("show_registration", False):
                st.caption(registration_text("returning_intro"))
                returning_phone = st.text_input(registration_text("phone"), placeholder=registration_text("phone_hint"), key="returning_phone")
                if st.button(registration_text("returning_send"), use_container_width=True, key="returning_otp_request"):
                    response, error = api_call("POST", "/auth/request-otp", json={"phone_number": returning_phone.strip()})
                    if error:
                        st.error(error)
                    elif response:
                        st.session_state.pending_returning_phone = returning_phone.strip()
                        st.session_state.pending_otp = response.get("otp")
                        st.session_state.login_step = "returning_otp"
                        st.rerun()
                if st.button(registration_text("new_registration"), use_container_width=True, key="open_registration"):
                    st.session_state.show_registration = True
                    st.rerun()
            else:
                render_new_farmer_registration()
        elif st.session_state.get("login_step") == "returning_otp":
            st.success(registration_text("sent"))
            if local_otp := st.session_state.get("pending_otp"):
                st.warning(registration_text("screen_otp").format(otp=local_otp))
            with st.form("returning_otp_verify_form"):
                otp = st.text_input(registration_text("otp"), max_chars=8, placeholder=registration_text("otp_hint"))
                verify = st.form_submit_button(registration_text("returning_verify"), use_container_width=True)
            if verify:
                phone_number = str(st.session_state.get("pending_returning_phone", ""))
                response, error = api_call(
                    "POST",
                    "/auth/verify-returning-otp",
                    json={"phone_number": phone_number, "otp": otp.strip()},
                )
                if error:
                    st.error(error)
                elif response:
                    st.session_state.logged_in = True
                    st.session_state.user_name = response["farmer"]["full_name"]
                    st.session_state.farmer_state = response["farmer"]["state"]
                    st.session_state.session_token = response["session_token"]
                    st.session_state.login_step = "profile"
                    st.session_state.pop("show_registration", None)
                    st.session_state.pop("pending_returning_phone", None)
                    st.session_state.pop("pending_otp", None)
                    st.rerun()
            if st.button(registration_text("back_to_registration"), use_container_width=True):
                st.session_state.login_step = "profile"
                st.session_state.pop("pending_returning_phone", None)
                st.session_state.pop("pending_otp", None)
                st.rerun()
        else:
            st.success(registration_text("sent"))
            if local_otp := st.session_state.get("pending_otp"):
                st.warning(registration_text("screen_otp").format(otp=local_otp))
            with st.form("otp_verify_form"):
                otp = st.text_input(registration_text("otp"), max_chars=8, placeholder=registration_text("otp_hint"))
                verify = st.form_submit_button(registration_text("verify"), use_container_width=True)
            if verify:
                profile = dict(st.session_state.get("pending_profile", {}))
                response, error = api_call("POST", "/auth/verify-otp", json={**profile, "otp": otp.strip()})
                if error:
                    st.error(error)
                elif response:
                    st.session_state.logged_in = True
                    st.session_state.user_name = response["farmer"]["full_name"]
                    st.session_state.farmer_state = response["farmer"]["state"]
                    st.session_state.session_token = response["session_token"]
                    st.session_state.login_step = "profile"
                    st.session_state.pop("show_registration", None)
                    st.session_state.pop("pending_profile", None)
                    st.session_state.pop("pending_otp", None)
                    st.rerun()
            if st.button(registration_text("edit")):
                st.session_state.login_step = "profile"
                st.session_state.pop("pending_otp", None)
                st.rerun()
    with right_posters:
        render_scheme_posters("right")
    if st.session_state.get("login_step", "profile") == "profile" and not st.session_state.get("show_registration", False):
        st.markdown("<br>", unsafe_allow_html=True)
        render_farmer_activity_map()
    st.markdown("<br>", unsafe_allow_html=True)
    render_how_it_works()
    st.markdown(f"<br><div class='eyebrow'>{tr('tools')}</div>", unsafe_allow_html=True)
    service_cards = (
        ("📷", tr("photo_title"), tr("photo_copy")),
        ("💧", tr("water_title"), tr("water_copy")),
        ("🧭", tr("state_title"), tr("state_copy")),
    )
    for column, (icon, title, copy) in zip(st.columns(3), service_cards):
        with column:
            st.markdown(f"<div class='service-card'><div class='service-icon'>{icon}</div><div class='service-title'>{title}</div><div class='service-copy'>{copy}</div></div>", unsafe_allow_html=True)
    st.markdown(f"<br><div class='eyebrow'>{tr('updates')}</div>", unsafe_allow_html=True)
    st.markdown(f"#### {tr('updates_heading')}")
    schemes = scheme_updates()
    for column, (title, summary, url) in zip(st.columns(3), schemes):
        with column:
            st.markdown(f"<div class='scheme-card'><div class='eyebrow'>{tr('official_update')}</div><div class='portal-name'>{title}</div><div class='portal-copy'>{summary}</div></div>", unsafe_allow_html=True)
            st.link_button(tr("read_update"), url, use_container_width=True)


def nutrient_card(label: str, value: float, status: str, unit: str = "kg/ha") -> str:
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value:.1f}</div><div class="metric-sub">{unit} • {status}</div></div>'


def admin_login_screen() -> None:
    """Separate entry point for authorised scheme administrators."""
    render_language_control()
    st.markdown("<div class='login-shell'><div class='brand'>Mitti<span>Mitra</span></div><div class='eyebrow'>authorised access</div><h2>Admin portal</h2><p>Verified government scheme updates ko manage karein.</p></div>", unsafe_allow_html=True)
    with st.form("admin_portal_login"):
        admin_key = st.text_input("Admin portal key", type="password", placeholder="SCHEME_ADMIN_KEY")
        login = st.form_submit_button("Open admin portal", icon=":material/login:", width="stretch")
    if login:
        clean_key = admin_key.strip()
        response, error = api_call("GET", "/admin/scheme-updates", headers={"X-Scheme-Admin-Key": clean_key})
        if error or response is None:
            st.error("Admin key verify nahi hua. `.env` ka SCHEME_ADMIN_KEY check karein.")
            return
        st.session_state.admin_access_key = clean_key
        st.session_state.scheme_admin_key = clean_key
        st.session_state.admin_authenticated = True
        st.rerun()
    if st.button("Farmer login par wapas", icon=":material/arrow_back:", width="stretch"):
        st.session_state.pop("admin_mode", None)
        st.rerun()


def admin_dashboard() -> None:
    """Keep scheme publishing away from the farmer-facing dashboard."""
    render_language_control()
    title, action = st.columns([5, 1])
    with title:
        st.markdown("<div class='brand'>Mitti<span>Mitra</span> <span style='font-size:.72rem'>ADMIN PORTAL</span></div>", unsafe_allow_html=True)
        st.caption("Only publish updates from official government sources. State targeting controls who sees the notice.")
    with action:
        if st.button("Sign out", icon=":material/logout:", width="stretch", key="admin_sign_out"):
            for key in ("admin_authenticated", "admin_access_key", "scheme_admin_key", "admin_mode"):
                st.session_state.pop(key, None)
            st.rerun()
    render_scheme_update_admin()


def render_state_resources() -> None:
    """Show services only for the state saved in the farmer's verified profile."""
    selected = str(st.session_state.get("farmer_state", "")).strip()
    st.markdown(f"<div class='eyebrow'>{tr('state_services')}</div>", unsafe_allow_html=True)
    st.markdown(f"#### {selected} {tr('portals')}")
    if selected not in STATE_PORTALS:
        st.info("Is registered state ke official scheme links abhi add kiye ja rahe hain. Tab tak MyScheme par apne state ki schemes search karein.")
        st.link_button("Open MyScheme ↗", "https://www.myscheme.gov.in/", use_container_width=True)
        return
    department, url = STATE_PORTALS[selected]
    resources = ((department, "Official agriculture department", url), *( (name, "Official farmer resource", resource_url) for name, resource_url in STATE_EXTRA_RESOURCES[selected]))
    for column, (name, description, resource_url) in zip(st.columns(3), resources):
        with column:
            st.markdown(f"<div class='resource-card'><div class='eyebrow'>{tr('official_resource')}</div><div class='portal-name'>{name}</div><div class='portal-copy'>{description} — {selected}.</div></div>", unsafe_allow_html=True)
            st.link_button(tr("open_portal"), resource_url, use_container_width=True)
    st.caption(tr("external_note"))


def render_scheme_update_admin() -> None:
    """Small protected publisher for official notices; it never scrapes or invents scheme news."""
    with st.expander("Official scheme update management", expanded=bool(st.session_state.get("admin_access_key"))):
        st.caption("Sirf verified official link ke saath update publish karein. Deadline ke baad update ticker se automatically hat jayega.")
        admin_key = st.text_input("Admin key", type="password", key="scheme_admin_key")
        if not admin_key:
            return
        headers = {"X-Scheme-Admin-Key": admin_key}
        with st.form("scheme_update_publish"):
            title = st.text_input("Update title", placeholder="Jaise: PMFBY Rabi enrolment — Haryana")
            summary = st.text_area("Short update", placeholder="Kis farmer ke liye hai aur unhe kya karna hai?")
            official_url = st.text_input("Official government link", placeholder="https://...")
            audience = st.selectbox("Audience", ["National (all farmers)", *location_options("/locations/states")])
            has_deadline = st.checkbox("Deadline add karein", value=True)
            deadline = st.date_input("Deadline", value=date.today()) if has_deadline else None
            publish = st.form_submit_button("Publish to ticker", use_container_width=True)
        if publish:
            payload = {"title": title.strip(), "summary": summary.strip(), "official_url": official_url.strip(), "target_state": None if audience.startswith("National") else audience, "deadline": deadline.isoformat() if deadline else None}
            response, error = api_call("POST", "/admin/scheme-updates", headers=headers, json=payload)
            if error:
                st.error(error)
            elif response:
                st.success("Update publish ho gaya. Yeh national ya selected state ke farmers ko ticker mein dikhega.")
        updates_response, list_error = api_call("GET", "/admin/scheme-updates", headers=headers)
        if list_error:
            st.caption("Admin key verify hone par published updates yahan dikhenge.")
            return
        for update in (updates_response or {}).get("items", []):
            if not isinstance(update, dict):
                continue
            title_line = f"{'●' if update.get('active') else '○'} {update.get('title')} — {update.get('target_state') or 'National'}"
            first, second = st.columns([5, 1])
            with first:
                st.caption(f"{title_line} | Deadline: {update.get('deadline') or 'None'}")
            with second:
                if update.get("active") and st.button("Remove", key=f"remove_update_{update.get('id')}"):
                    _, remove_error = api_call("DELETE", f"/admin/scheme-updates/{update.get('id')}", headers=headers)
                    if remove_error:
                        st.error(remove_error)
                    else:
                        st.rerun()


def render_profile_corner() -> None:
    """A compact, editable farmer profile in the dashboard's top-right corner."""
    token = str(st.session_state.get("session_token", ""))
    farmer, error = api_call("GET", "/me", headers={"X-Session-Token": token})
    if error or not farmer:
        return
    language = language_mode()
    labels = {
        "Hindi": ("मेरी जानकारी", "ज़मीन या पता बदलने पर जानकारी अपडेट करें।", "नाम", "उम्र", "ज़मीन", "इकाई", "राज्य", "ज़िला", "तहसील", "गाँव", "सुरक्षित करें", "जानकारी अपडेट हो गई।"),
        "Hinglish": ("Meri details", "Zameen ya location badalne par details update karein.", "Naam", "Umar", "Zameen", "Unit", "Rajya", "Jila", "Tehsil", "Gaon", "Save karein", "Details update ho gayi."),
        "English": ("My details", "Update your land holding or location when it changes.", "Name", "Age", "Land", "Unit", "State", "District", "Tehsil", "Village", "Save details", "Details updated."),
    }[language]
    with st.popover(labels[0], icon=":material/account_circle:", width="content", key="profile_corner"):
        st.caption(labels[1])
        with st.form("profile_corner_form"):
            full_name = st.text_input(labels[2], value=str(farmer["full_name"]), key="corner_full_name")
            age, land_size = st.columns(2)
            with age:
                age_value = st.number_input(labels[3], min_value=14, max_value=120, value=int(farmer["age"]), key="corner_age")
            with land_size:
                land_value = st.number_input(labels[4], min_value=0.1, max_value=100000.0, value=float(farmer["land_size"]), step=0.1, key="corner_land")
            land_unit = st.text_input(labels[5], value=str(farmer["land_unit"]), key="corner_unit")
            state_value = st.text_input(labels[6], value=str(farmer["state"]), key="corner_state")
            district_value = st.text_input(labels[7], value=str(farmer["district"]), key="corner_district")
            tehsil_value = st.text_input(labels[8], value=str(farmer["city"]), key="corner_tehsil")
            village_value = st.text_input(labels[9], value=str(farmer["village"]), key="corner_village")
            st.caption(f"OTP mobile: {farmer['phone_number']}")
            saved = st.form_submit_button(labels[10], icon=":material/save:", width="stretch")
        if saved:
            payload = {
                "full_name": full_name.strip(), "age": int(age_value), "land_size": float(land_value), "land_unit": land_unit.strip(),
                "state": state_value.strip(), "district": district_value.strip(), "tehsil": tehsil_value.strip(), "village": village_value.strip(),
                "scheme_sms_opt_in": bool(farmer.get("scheme_sms_opt_in", False)), "small_farm_updates": bool(farmer.get("small_farm_updates", False)),
            }
            updated, update_error = api_call("PUT", "/me", headers={"X-Session-Token": token}, json=payload)
            if update_error:
                st.error(update_error)
            elif updated:
                st.session_state.user_name = str(updated["full_name"])
                st.session_state.farmer_state = str(updated["state"])
                st.success(labels[11])


def render_kisan_mitra_floating() -> None:
    """Always-visible right-side AI conversation panel for logged-in farmers."""
    token = str(st.session_state.get("session_token", ""))
    if not token:
        return
    language = language_mode()
    labels = {
        "Hindi": {
            "title": "किसान मित्र AI", "copy": "खेती, मौसम या पशु-चारा के बारे में पूछें।", "topic": "विषय", "general": "खेती / मिट्टी", "livestock": "भैंस / पशु चारा", "weather": "फसल + स्थानीय मौसम", "question": "अपना सवाल", "placeholder": "जैसे: दूध बढ़ाने के लिए भैंस को कौन-सा संतुलित चारा दें?", "send": "AI से पूछें", "voice": "आवाज़ से पूछें", "speak": "AI का जवाब आवाज़ में सुनें", "consent": "मौसम सलाह के लिए मेरा ज़िला और राज्य उपयोग करें", "warning": "बीमार पशु या आपात स्थिति में पशु चिकित्सक से तुरंत संपर्क करें।",
        },
        "Hinglish": {
            "title": "Kisan Mitra AI", "copy": "Kheti, weather ya pashu-chara ke baare mein poochhein.", "topic": "Topic", "general": "Kheti / mitti", "livestock": "Bhains / pashu chara", "weather": "Fasal + local weather", "question": "Apna sawaal", "placeholder": "Jaise: doodh badhane ke liye bhains ko kaunsa balanced chara dein?", "send": "AI se poochhein", "voice": "Awaaz se poochhein", "speak": "AI ka jawab awaaz mein sunein", "consent": "Weather advice ke liye mera district aur state use karein", "warning": "Beemar pashu ya emergency mein veterinarian se turant baat karein.",
        },
        "English": {
            "title": "Kisan Mitra AI", "copy": "Ask about farming, weather or animal feed.", "topic": "Topic", "general": "Farming / soil", "livestock": "Buffalo / animal feed", "weather": "Crop + local weather", "question": "Your question", "placeholder": "For example: What balanced feed should I give my buffalo to support milk production?", "send": "Ask AI", "voice": "Ask by voice", "speak": "Play the AI answer aloud", "consent": "Use my district and state for weather advice", "warning": "For a sick animal or emergency, contact a qualified veterinarian immediately.",
        },
    }[language]
    messages_key = "kisan_mitra_ai_messages"
    st.session_state.setdefault(messages_key, [])
    messages = st.session_state[messages_key]
    quick_prompts = {
        "Hindi": {
            "आज के मौसम में क्या करें?": "मेरे जिले के अगले कुछ दिनों के मौसम के अनुसार खेत में क्या सावधानी रखनी चाहिए?",
            "भैंस के चारे की सलाह": "दूध उत्पादन के लिए भैंस को संतुलित चारे में क्या देना चाहिए?",
            "बारिश के बाद खेत": "बारिश के बाद खेत में सबसे पहले क्या देखना और क्या करना चाहिए?",
        },
        "Hinglish": {
            "Aaj ke mausam ki salah": "Mere district ke agle kuch din ke weather ke hisaab se khet mein kya savdhani rakhni chahiye?",
            "Bhains ke chara ki salah": "Doodh production ke liye bhains ko balanced chara mein kya dena chahiye?",
            "Baarish ke baad khet": "Baarish ke baad khet mein sabse pehle kya dekhna aur kya karna chahiye?",
        },
        "English": {
            "Weather advice": "What field precautions should I take based on the next few days of weather in my district?",
            "Buffalo feed advice": "What should I include in a balanced buffalo ration to support milk production?",
            "After rainfall": "What should I inspect and do first in my field after rainfall?",
        },
    }[language]

    with st.container(border=True, key="kisan_mitra_floating", height=550, autoscroll=True, gap="xsmall"):
        farmer_name = escape(str(st.session_state.get("user_name", "किसान भाई")))
        st.markdown(
            f"""<section class='ai-float-hero'><div class='ai-float-title-row'><div class='ai-float-avatar'>🌾</div><div><div class='ai-float-title'>{labels['title']}</div><div class='ai-float-status'><i></i>AI सहायक तैयार है</div></div></div><p>नमस्ते {farmer_name}! आज खेती, मौसम या पशु-चारा में किस बात की मदद चाहिए?</p></section>""",
            unsafe_allow_html=True,
        )
        st.caption(labels["warning"])
        quick_pick = None
        if not messages:
            st.caption("झटपट शुरू करें")
            quick_pick = st.pills("Quick questions", list(quick_prompts), key="floating_ai_quick_prompts", label_visibility="collapsed", width="stretch")
        with st.container(key="ai_chat_history", height=145, border=False, autoscroll=True, gap="xxsmall"):
            if messages:
                for message in messages[-4:]:
                    with st.chat_message(str(message["role"]), avatar=":material/smart_toy:" if message["role"] == "assistant" else ":material/agriculture:"):
                        st.write(str(message["content"]))
                        if message.get("audio"):
                            st.audio(base64.b64decode(str(message["audio"])), format=str(message.get("mime_type", "audio/wav")))
            else:
                st.caption("अपना सवाल लिखें या ऊपर दिया गया कोई सुझाव चुनें।")
        topic_labels = {labels["general"]: "general", labels["livestock"]: "livestock", labels["weather"]: "crop_weather"}
        selected_label = st.selectbox(labels["topic"], list(topic_labels), key="floating_ai_topic")
        request_type = topic_labels[selected_label]
        weather_ok = request_type != "crop_weather" or st.checkbox(labels["consent"], key="floating_ai_weather_consent")
        speak_reply = st.checkbox(labels["speak"], value=True, key="floating_ai_speak_reply")

        def ask(question: str) -> None:
            clean_question = question.strip()
            if len(clean_question) < 2:
                st.error(labels["question"])
                return
            if request_type == "crop_weather" and not weather_ok:
                st.error(labels["consent"])
                return
            messages.append({"role": "user", "content": clean_question})
            with st.spinner("Kisan Mitra AI soch raha hai..."):
                advice, advice_error = api_call("POST", "/assistant/advice", headers={"X-Session-Token": token}, json={"question": clean_question, "language": language, "request_type": request_type})
            if advice_error or not advice:
                messages.append({"role": "assistant", "content": advice_error or "AI answer unavailable."})
            else:
                answer = str(advice.get("answer", ""))
                reply: dict[str, object] = {"role": "assistant", "content": answer}
                if speak_reply:
                    speech, speech_error = api_call("POST", "/assistant/speak", headers={"X-Session-Token": token}, json={"text": answer})
                    if speech and not speech_error:
                        reply["audio"] = str(speech.get("audio_base64", ""))
                        reply["mime_type"] = str(speech.get("mime_type", "audio/wav"))
                messages.append(reply)
            st.rerun()

        if quick_pick:
            ask(quick_prompts[str(quick_pick)])
        with st.form("floating_ai_text_form", border=False):
            typed_question = st.text_area(labels["question"], placeholder=labels["placeholder"], max_chars=700, key="floating_ai_text")
            submitted = st.form_submit_button(labels["send"], icon=":material/send:", width="stretch")
        if submitted:
            ask(typed_question)
        audio_question = st.audio_input(labels["voice"], key="floating_ai_audio")
        if st.button(labels["voice"], icon=":material/mic:", width="stretch", key="floating_ai_voice_send", disabled=audio_question is None):
            if audio_question is not None:
                with st.spinner("Aapki awaaz samajh raha hai..."):
                    transcript, transcript_error = api_call("POST", "/assistant/transcribe", headers={"X-Session-Token": token}, data={"language": language}, files={"audio": (audio_question.name, audio_question.getvalue(), audio_question.type)})
                if transcript_error or not transcript:
                    st.error(transcript_error or "Voice transcription unavailable.")
                else:
                    ask(str(transcript.get("transcript", "")))


def render_account_and_lab_tools() -> None:
    """Farmer-owned profile editing plus an official, location-specific lab finder."""
    token = st.session_state.get("session_token", "")
    farmer, error = api_call("GET", "/me", headers={"X-Session-Token": token})
    if error or not farmer:
        return
    language = language_mode()
    labels = {
        "Hindi": {
            "profile": "मेरी जानकारी", "lab": "नज़दीकी मिट्टी जाँच लैब", "profile_intro": "अपनी ज़मीन या पता बदलने पर यहाँ जानकारी अपडेट करें। मोबाइल नंबर OTP से सत्यापित है, इसलिए यहाँ नहीं बदलेगा।",
            "save": "जानकारी सुरक्षित करें", "saved": "जानकारी अपडेट हो गई।", "lab_title": "{district}, {state} में मिट्टी जाँच लैब खोजें", "lab_copy": "आपके पंजीकृत ज़िले के अनुसार खोज तैयार है। अंतिम लैब पता, शुल्क और समय सीधे आधिकारिक पोर्टल या लैब से पुष्टि करें।",
            "official": "सरकारी Soil Health Card लैब डायरेक्टरी खोलें ↗", "maps": "मैप में नज़दीकी लैब खोजें ↗", "phone": "सत्यापित मोबाइल नंबर", "name": "किसान का नाम", "age": "उम्र", "land": "ज़मीन का क्षेत्र", "unit": "ज़मीन की इकाई", "state": "राज्य", "district": "ज़िला / शहर", "tehsil": "तहसील", "village": "गाँव", "sms": "सरकारी योजना की SMS सूचनाएँ", "small": "छोटी जोत की योजनाओं की सूचना",
        },
        "Hinglish": {
            "profile": "Meri details", "lab": "Najdeeki soil test lab", "profile_intro": "Zameen ya location badalne par yahan details update karein. Mobile OTP se verified hai, isliye yahan change nahi hoga.",
            "save": "Details save karein", "saved": "Details update ho gayi.", "lab_title": "{district}, {state} mein soil test lab dhoondhein", "lab_copy": "Aapke registered district ke hisaab se search ready hai. Final address, fee aur timings official portal ya lab se confirm karein.",
            "official": "Official Soil Health Card lab directory kholein ↗", "maps": "Map mein najdeeki labs dekhein ↗", "phone": "Verified mobile number", "name": "Kisaan ka naam", "age": "Umar", "land": "Land area", "unit": "Land unit", "state": "Rajya", "district": "Jila / City", "tehsil": "Tehsil", "village": "Gaon", "sms": "Government scheme SMS updates", "small": "Chhoti joat scheme updates",
        },
        "English": {
            "profile": "My details", "lab": "Nearby soil test lab", "profile_intro": "Update this information when your land holding or location changes. Your OTP-verified mobile number cannot be changed here.",
            "save": "Save details", "saved": "Your details have been updated.", "lab_title": "Find soil test labs in {district}, {state}", "lab_copy": "The search is prepared using your registered district. Confirm the final address, fee and hours with the official portal or laboratory.",
            "official": "Open the official Soil Health Card lab directory ↗", "maps": "See nearby labs on the map ↗", "phone": "Verified mobile number", "name": "Farmer name", "age": "Age", "land": "Land area", "unit": "Land unit", "state": "State", "district": "District / City", "tehsil": "Tehsil", "village": "Village", "sms": "Government-scheme SMS updates", "small": "Small-holder scheme updates",
        },
    }[language]
    lease_text = {
        "Hindi": {
            "tab": "भूमि पट्टा", "title": "कृषि भूमि पट्टा सहायता", "copy": "बड़ी जोत वाले किसान अपनी खाली भूमि के पट्टे के लिए रुचि दर्ज कर सकते हैं। छोटे किसान अपने ज़िले की उपलब्ध भूमि देख सकते हैं।",
            "owner": "भूमि मालिक", "cultivator": "खेती करने वाला किसान", "platform": "MittiMitra समन्वय", "terms": "साझेदारी का प्रस्ताव", "terms_copy": "खेती से शुद्ध आय का प्रस्तावित बँटवारा: भूमि मालिक 48%, खेती करने वाला किसान 48%, और MittiMitra समन्वय शुल्क 4%। यह केवल प्रारंभिक प्रस्ताव है, कानूनी अनुबंध नहीं।",
            "list": "अपनी भूमि सूचीबद्ध करें", "browse": "नज़दीकी अवसर देखें", "area": "पट्टे पर उपलब्ध भूमि", "period": "पट्टा अवधि (महीने)", "crop": "पसंदीदा फसल (वैकल्पिक)", "note": "भूमि/सिंचाई की जानकारी (वैकल्पिक)", "consent": "मैं पुष्टि करता/करती हूँ कि यह मेरी भूमि है और मैं केवल रुचि दर्ज कर रहा/रही हूँ।", "submit": "पट्टा अवसर प्रकाशित करें", "published": "आपकी पट्टा-रुचि सुरक्षित हो गई।", "nearby": "{district}, {state} के अवसर", "empty": "आपके ज़िले में अभी कोई पट्टा अवसर नहीं है।", "interest": "रुचि दर्ज करें", "recorded": "रुचि दर्ज हो गई। आगे की बात केवल सत्यापन और सहमति के बाद होगी।", "legal": "MittiMitra अभी केवल किसान-मिलान का प्रोटोटाइप है। यह भूमि का कब्ज़ा, भुगतान या कानूनी पट्टा अनुबंध नहीं करता। रजिस्टर्ड लिखित अनुबंध, भूमि सत्यापन और स्थानीय कानूनी सलाह आवश्यक हैं।",
        },
        "Hinglish": {
            "tab": "Land lease", "title": "Kheti land lease support", "copy": "Badi joat wale kisaan apni available land ke liye interest list kar sakte hain. Chhote kisaan apne district ke available opportunities dekh sakte hain.",
            "owner": "Landholder", "cultivator": "Cultivating farmer", "platform": "MittiMitra coordination", "terms": "Proposed share", "terms_copy": "Kheti ki net income ka proposed split: landholder 48%, kheti karne wala farmer 48%, aur MittiMitra coordination fee 4%. Yeh sirf initial proposal hai, legal contract nahi.",
            "list": "Apni land list karein", "browse": "Najdeeki opportunities dekhein", "area": "Land available for lease", "period": "Lease duration (months)", "crop": "Preferred crop (optional)", "note": "Land / irrigation note (optional)", "consent": "Main confirm karta/karti hoon ki yeh meri land hai aur main sirf interest list kar raha/rahi hoon.", "submit": "Lease opportunity publish karein", "published": "Aapki lease interest safely save ho gayi.", "nearby": "{district}, {state} opportunities", "empty": "Aapke district mein abhi koi lease opportunity nahi hai.", "interest": "Interest register karein", "recorded": "Interest register ho gaya. Aage ki baat sirf verification aur mutual consent ke baad hogi.", "legal": "MittiMitra abhi farmer-matching prototype hai. Yeh land possession, payment ya legal lease agreement execute nahi karta. Written registered agreement, land verification aur local legal advice zaroori hai.",
        },
        "English": {
            "tab": "Land lease", "title": "Farm land lease support", "copy": "Large landholders can list land they are interested in leasing. Small farmers can browse opportunities in their district.",
            "owner": "Landholder", "cultivator": "Cultivating farmer", "platform": "MittiMitra coordination", "terms": "Proposed share", "terms_copy": "Proposed net-income split from cultivation: 48% landholder, 48% cultivating farmer and 4% MittiMitra coordination fee. This is an initial proposal, not a legal contract.",
            "list": "List my land", "browse": "Browse nearby opportunities", "area": "Land available for lease", "period": "Lease duration (months)", "crop": "Preferred crop (optional)", "note": "Land / irrigation note (optional)", "consent": "I confirm that this is my land and I am only registering my interest in listing it.", "submit": "Publish lease opportunity", "published": "Your lease interest has been saved.", "nearby": "Opportunities in {district}, {state}", "empty": "There are no lease opportunities in your district yet.", "interest": "Register interest", "recorded": "Interest recorded. Further discussion happens only after verification and mutual consent.", "legal": "MittiMitra is currently a farmer-matching prototype. It does not take possession of land, accept payments, or execute a legal lease. A written registered agreement, land verification, and local legal advice are essential.",
        },
    }[language]
    ai_text = {
        "Hindi": {
            "tab": "किसान मित्र AI", "title": "किसान मित्र AI सहायक", "copy": "आवाज़ या लिखकर खेती, मौसम और पशु-चारा के बारे में पूछें।", "type": "सलाह का विषय", "general": "खेती / मिट्टी", "livestock": "भैंस / पशु चारा", "weather": "फसल + स्थानीय मौसम", "question": "अपना सवाल लिखें", "placeholder": "जैसे: मेरी भैंस के दूध के लिए संतुलित चारे में क्या ध्यान रखूँ?", "ask": "AI से पूछें", "record": "अपनी बात रिकॉर्ड करें", "voice": "आवाज़ से सवाल भेजें", "voice_hint": "रिकॉर्डिंग केवल लिखित सवाल बनाने के लिए भेजी जाती है; इसे सर्वर पर सेव नहीं किया जाता।", "weather_consent": "मैं सहमत हूँ कि केवल मौसम सलाह के लिए मेरा पंजीकृत ज़िला और राज्य Open-Meteo को भेजा जाए।", "weather_hint": "मौसम सलाह 7-दिन के पूर्वानुमान पर है, पूरे मौसम की गारंटी नहीं।", "listen": "AI की आवाज़ में जवाब सुनाएँ", "transcript": "आपका बोला हुआ सवाल", "disclaimer": "यह AI सामान्य मार्गदर्शन है—लाभ/उपज की गारंटी नहीं। बीमार पशु, अचानक दूध कम होना, बुखार या आपात स्थिति में तुरंत पशु चिकित्सक से संपर्क करें। फसल में खर्च करने से पहले KVK/कृषि विभाग से पुष्टि करें।", "empty": "यहाँ आपका किसान मित्र AI संवाद दिखेगा।",
        },
        "Hinglish": {
            "tab": "Kisan Mitra AI", "title": "Kisan Mitra AI assistant", "copy": "Awaaz ya likhkar kheti, mausam aur pashu-chara ke baare mein poochhein.", "type": "Advice topic", "general": "Kheti / mitti", "livestock": "Bhains / pashu chara", "weather": "Fasal + local weather", "question": "Apna sawaal likhein", "placeholder": "Jaise: meri bhains ke doodh ke liye balanced chara mein kya dhyan rakhoon?", "ask": "AI se poochhein", "record": "Apni baat record karein", "voice": "Awaaz se sawaal bhejein", "voice_hint": "Recording sirf written question banane ke liye bheji jaati hai; server par save nahi hoti.", "weather_consent": "Main maanta/maanti hoon ki sirf weather advice ke liye mera registered district aur state Open-Meteo ko bheja jaaye.", "weather_hint": "Weather advice 7-day forecast par hoti hai, poore season ki guarantee nahi.", "listen": "AI voice mein jawab sunaayein", "transcript": "Aapka bola hua sawaal", "disclaimer": "Yeh AI general guidance hai—profit/yield ki guarantee nahi. Beemar pashu, achanak doodh kam hona, bukhar ya emergency mein turant veterinarian se baat karein. Crop par kharch karne se pehle KVK/agriculture department se confirm karein.", "empty": "Aapka Kisan Mitra AI conversation yahan dikhega.",
        },
        "English": {
            "tab": "Kisan Mitra AI", "title": "Kisan Mitra AI assistant", "copy": "Ask by voice or text about farming, weather and animal feed.", "type": "Advice topic", "general": "Farming / soil", "livestock": "Buffalo / animal feed", "weather": "Crop + local weather", "question": "Write your question", "placeholder": "For example: What should I keep in mind for a balanced ration for my buffalo's milk production?", "ask": "Ask AI", "record": "Record your question", "voice": "Send voice question", "voice_hint": "The recording is sent only to make a written question; it is not saved on this server.", "weather_consent": "I agree that my registered district and state may be sent to Open-Meteo only for weather advice.", "weather_hint": "Weather advice uses a 7-day forecast and is not a full-season guarantee.", "listen": "Play AI voice reply", "transcript": "Your spoken question", "disclaimer": "This is general AI guidance, not a profit/yield guarantee. For a sick animal, sudden milk drop, fever or emergency, contact a qualified veterinarian immediately. Confirm crop spending decisions with a KVK or agriculture department.", "empty": "Your Kisan Mitra AI conversation will appear here.",
        },
    }[language]
    with st.container(key="lab_lease_area", border=False):
        st.markdown(f"#### {labels['lab']} · {lease_text['tab']}")
        st.caption("Location-based soil lab support aur verified land-lease opportunities ek jagah.")
    lab_tab, lease_tab = st.tabs([f":material/science: {labels['lab']}", f":material/agriculture: {lease_text['tab']}"])
    if False:  # Profile editing now lives in the top-right "My details" popover.
        st.caption(labels["profile_intro"])
        with st.form("farmer_profile_update"):
            first, second = st.columns(2)
            with first:
                full_name = st.text_input(labels["name"], value=str(farmer["full_name"]))
                age = st.number_input(labels["age"], min_value=14, max_value=120, value=int(farmer["age"]), step=1)
            with second:
                land_size = st.number_input(labels["land"], min_value=0.1, max_value=100000.0, value=float(farmer["land_size"]), step=0.1)
                land_unit = st.text_input(labels["unit"], value=str(farmer["land_unit"]))
            state, district, tehsil, village = st.columns(4)
            with state:
                state_value = st.text_input(labels["state"], value=str(farmer["state"]))
            with district:
                district_value = st.text_input(labels["district"], value=str(farmer["district"]))
            with tehsil:
                tehsil_value = st.text_input(labels["tehsil"], value=str(farmer["city"]))
            with village:
                village_value = st.text_input(labels["village"], value=str(farmer["village"]))
            st.caption(f"{labels['phone']}: {farmer['phone_number']}")
            sms = st.checkbox(labels["sms"], value=bool(farmer.get("scheme_sms_opt_in", False)))
            small = st.checkbox(labels["small"], value=bool(farmer.get("small_farm_updates", False)), disabled=not sms)
            saved = st.form_submit_button(labels["save"], use_container_width=True)
        if saved:
            payload = {"full_name": full_name.strip(), "age": int(age), "land_size": float(land_size), "land_unit": land_unit.strip(), "state": state_value.strip(), "district": district_value.strip(), "tehsil": tehsil_value.strip(), "village": village_value.strip(), "scheme_sms_opt_in": sms, "small_farm_updates": small}
            updated, update_error = api_call("PUT", "/me", headers={"X-Session-Token": token}, json=payload)
            if update_error:
                st.error(update_error)
            elif updated:
                st.session_state.user_name = str(updated["full_name"])
                st.session_state.farmer_state = str(updated["state"])
                st.success(labels["saved"])
    with lab_tab:
        district_value, state_value = str(farmer["district"]), str(farmer["state"])
        query = quote_plus(f"soil testing laboratory {district_value} {state_value} India")
        st.markdown(f"#### {labels['lab_title'].format(district=escape(district_value), state=escape(state_value))}")
        st.info(labels["lab_copy"])
        first, second = st.columns(2)
        with first:
            st.link_button(labels["official"], "https://soilhealth.dac.gov.in/soil-lab", use_container_width=True)
        with second:
            st.link_button(labels["maps"], f"https://www.google.com/maps/search/?api=1&query={query}", use_container_width=True)
        st.caption("Source: Government of India Soil Health Card portal. It provides contact details for nearest soil-testing laboratories.")
    with lease_tab:
        st.markdown(f"#### {lease_text['title']}")
        st.caption(lease_text["copy"])
        st.info(lease_text["legal"])
        st.markdown(f"**{lease_text['terms']}**")
        split_owner, split_farmer, split_platform = st.columns(3)
        split_owner.metric(lease_text["owner"], "48%")
        split_farmer.metric(lease_text["cultivator"], "48%")
        split_platform.metric(lease_text["platform"], "4%")
        st.caption(lease_text["terms_copy"])

        list_tab, browse_tab = st.tabs([lease_text["list"], lease_text["browse"]])
        with list_tab:
            with st.form("lease_listing_form"):
                first, second = st.columns(2)
                with first:
                    listed_area = st.number_input(lease_text["area"], min_value=0.1, max_value=100000.0, value=float(farmer["land_size"]), step=0.1)
                    listed_unit = st.text_input(labels["unit"], value=str(farmer["land_unit"]), key="lease_land_unit")
                with second:
                    duration = st.number_input(lease_text["period"], min_value=6, max_value=60, value=12, step=1)
                    crop_preference = st.text_input(lease_text["crop"], key="lease_crop")
                st.caption(f"{farmer['village']}, {farmer['city']}, {farmer['district']}, {farmer['state']}")
                listing_note = st.text_area(lease_text["note"], max_chars=500, key="lease_note")
                consent = st.checkbox(lease_text["consent"], key="lease_consent")
                publish = st.form_submit_button(lease_text["submit"], width="stretch")
            if publish:
                if not consent:
                    st.error(lease_text["consent"])
                else:
                    payload = {
                        "land_size": float(listed_area), "land_unit": listed_unit.strip(), "state": str(farmer["state"]),
                        "district": str(farmer["district"]), "tehsil": str(farmer["city"]), "village": str(farmer["village"]),
                        "duration_months": int(duration), "crop_preference": crop_preference.strip() or None, "notes": listing_note.strip() or None,
                    }
                    created, create_error = api_call("POST", "/lease-listings", headers={"X-Session-Token": token}, json=payload)
                    if create_error:
                        st.error(create_error)
                    elif created:
                        st.success(lease_text["published"])
        with browse_tab:
            district_value, state_value = str(farmer["district"]), str(farmer["state"])
            st.markdown(f"**{lease_text['nearby'].format(district=district_value, state=state_value)}**")
            opportunities, listing_error = api_call("GET", "/lease-listings", headers={"X-Session-Token": token}, params={"state": state_value, "district": district_value})
            if listing_error:
                st.error(listing_error)
            else:
                items = list((opportunities or {}).get("items", []))
                viewer_id = str((opportunities or {}).get("viewer_id", ""))
                if not items:
                    st.caption(lease_text["empty"])
                for item in items:
                    with st.container(border=True):
                        st.markdown(f"**{item['land_size']} {escape(str(item['land_unit']))}** · {item['duration_months']} months")
                        st.caption(f"{item['village']}, {item['tehsil']} · {item['district']}, {item['state']}")
                        if item.get("crop_preference"):
                            st.write(f"{lease_text['crop']}: {item['crop_preference']}")
                        if item.get("notes"):
                            st.caption(str(item["notes"]))
                        if str(item.get("farmer_id", "")) == viewer_id:
                            st.caption(f"{item.get('interest_count', 0)} verified farmer interest(s)")
                        elif st.button(lease_text["interest"], key=f"lease_interest_{item['id']}"):
                            result, interest_error = api_call("POST", f"/lease-listings/{item['id']}/interest", headers={"X-Session-Token": token})
                            if interest_error:
                                st.error(interest_error)
                            elif result:
                                st.success(lease_text["recorded"])
    if False:  # The live AI chat now opens automatically as the right-side panel.
        st.markdown(f"#### {ai_text['title']}")
        st.caption(ai_text["copy"])
        st.info(ai_text["disclaimer"])
        messages_key = "kisan_mitra_ai_messages"
        st.session_state.setdefault(messages_key, [])
        messages = st.session_state[messages_key]
        if messages:
            for message in messages:
                with st.chat_message(str(message["role"]), avatar="🤖" if message["role"] == "assistant" else "🧑🏽‍🌾"):
                    st.write(str(message["content"]))
                    if message.get("audio"):
                        st.audio(base64.b64decode(str(message["audio"])), format=str(message.get("mime_type", "audio/wav")))
        else:
            st.caption(ai_text["empty"])

        topic_labels = {ai_text["general"]: "general", ai_text["livestock"]: "livestock", ai_text["weather"]: "crop_weather"}
        selected_label = st.selectbox(ai_text["type"], list(topic_labels), key="kisan_mitra_topic")
        request_type = topic_labels[selected_label]
        weather_ok = True
        if request_type == "crop_weather":
            st.caption(ai_text["weather_hint"])
            weather_ok = st.checkbox(ai_text["weather_consent"], key="kisan_mitra_weather_consent")
        speak_reply = st.checkbox(ai_text["listen"], value=True, key="kisan_mitra_speak_reply")

        def ask_kisan_mitra(question: str) -> None:
            clean_question = question.strip()
            if len(clean_question) < 2:
                st.error(ai_text["question"])
                return
            if request_type == "crop_weather" and not weather_ok:
                st.error(ai_text["weather_consent"])
                return
            messages.append({"role": "user", "content": clean_question})
            with st.spinner("Kisan Mitra AI soch raha hai..."):
                advice, advice_error = api_call(
                    "POST", "/assistant/advice", headers={"X-Session-Token": token},
                    json={"question": clean_question, "language": language, "request_type": request_type},
                )
            if advice_error or not advice:
                messages.append({"role": "assistant", "content": advice_error or "AI answer unavailable."})
                st.rerun()
            answer = str(advice.get("answer", ""))
            reply: dict[str, object] = {"role": "assistant", "content": answer}
            if speak_reply:
                speech, speech_error = api_call("POST", "/assistant/speak", headers={"X-Session-Token": token}, json={"text": answer})
                if speech and not speech_error:
                    reply["audio"] = str(speech.get("audio_base64", ""))
                    reply["mime_type"] = str(speech.get("mime_type", "audio/wav"))
            messages.append(reply)
            st.rerun()

        with st.form("kisan_mitra_text_question"):
            typed_question = st.text_area(ai_text["question"], placeholder=ai_text["placeholder"], max_chars=1200)
            ask_typed = st.form_submit_button(ai_text["ask"], use_container_width=True)
        if ask_typed:
            ask_kisan_mitra(typed_question)

        st.markdown(f"**{ai_text['record']}**")
        st.caption(ai_text["voice_hint"])
        audio_question = st.audio_input(ai_text["record"], key="kisan_mitra_audio")
        if audio_question is not None:
            st.audio(audio_question)
        if st.button(ai_text["voice"], use_container_width=True, key="kisan_mitra_voice_send", disabled=audio_question is None):
            if request_type == "crop_weather" and not weather_ok:
                st.error(ai_text["weather_consent"])
            elif audio_question is not None:
                with st.spinner("Aapki awaaz samajh raha hai..."):
                    transcript, transcript_error = api_call(
                        "POST", "/assistant/transcribe", headers={"X-Session-Token": token},
                        data={"language": language}, files={"audio": (audio_question.name, audio_question.getvalue(), audio_question.type)},
                    )
                if transcript_error or not transcript:
                    st.error(transcript_error or "Voice transcript unavailable.")
                else:
                    spoken_question = str(transcript.get("transcript", ""))
                    st.caption(f"{ai_text['transcript']}: {spoken_question}")
                    ask_kisan_mitra(spoken_question)


def localize_agriculture_text(value: object, language: str) -> str:
    """Keep map crop/soil values in the same language as the selected UI."""
    text = str(value or "")
    if language == "English":
        return text
    hindi = {
        "Coconut": "नारियल", "arecanut": "सुपारी", "rice": "धान", "Rice": "धान",
        "cotton": "कपास", "Cotton": "कपास", "chilli": "मिर्च", "Chilli": "मिर्च",
        "maize": "मक्का", "Maize": "मक्का", "millets": "मोटे अनाज", "Millets": "मोटे अनाज",
        "tea": "चाय", "Tea": "चाय", "jute": "जूट", "Jute": "जूट", "wheat": "गेहूँ", "Wheat": "गेहूँ",
        "mango": "आम", "Mango": "आम", "vegetables": "सब्जियाँ", "Vegetables": "सब्जियाँ",
        "mustard": "सरसों", "Mustard": "सरसों", "cashew": "काजू", "Cashew": "काजू",
        "groundnut": "मूंगफली", "Groundnut": "मूंगफली", "bajra": "बाजरा", "Bajra": "बाजरा",
        "apple": "सेब", "Apple": "सेब", "pulses": "दालें", "Pulses": "दालें", "ragi": "रागी", "Ragi": "रागी",
        "coffee": "कॉफी", "Coffee": "कॉफी", "rubber": "रबर", "Rubber": "रबर", "spices": "मसाले", "Spices": "मसाले",
        "barley": "जौ", "Barley": "जौ", "peas": "मटर", "Peas": "मटर", "soybean": "सोयाबीन", "Soybean": "सोयाबीन",
        "gram": "चना", "Gram": "चना", "sugarcane": "गन्ना", "Sugarcane": "गन्ना", "potato": "आलू", "Potato": "आलू",
        "ginger": "अदरक", "Ginger": "अदरक", "oilseeds": "तिलहन", "Oilseeds": "तिलहन",
        "Large cardamom": "बड़ी इलायची", "large cardamom": "बड़ी इलायची", "pineapple": "अनानास", "Pineapple": "अनानास",
        "Coastal alluvial": "तटीय जलोढ़", "coastal alluvial": "तटीय जलोढ़", "Alluvial": "जलोढ़", "alluvial": "जलोढ़",
        "Laterite": "लेटराइट", "laterite": "लेटराइट", "Forest": "वन", "forest": "वन", "Mountain": "पर्वतीय", "mountain": "पर्वतीय",
        "Red-yellow": "लाल-पीली", "red-yellow": "लाल-पीली", "Red": "लाल", "red": "लाल", "Black": "काली", "black": "काली",
        "desert": "रेगिस्तानी", "Desert": "रेगिस्तानी", "saline-alkaline": "लवणीय-क्षारीय", "Coral sand": "मूंगा रेत",
        "coastal": "तटीय", "Coastal": "तटीय", "terai": "तराई", "Terai": "तराई",
    }
    hinglish = {
        "नारियल": "nariyal", "सुपारी": "supari", "धान": "dhan", "कपास": "kapas", "मिर्च": "mirch", "मक्का": "makka",
        "मोटे अनाज": "mote anaaj", "चाय": "chai", "जूट": "jute", "गेहूँ": "gehu", "आम": "aam", "सब्जियाँ": "sabziyan",
        "सरसों": "sarson", "काजू": "kaju", "मूंगफली": "moongfali", "बाजरा": "bajra", "सेब": "seb", "दालें": "daalen",
        "रागी": "ragi", "कॉफी": "coffee", "रबर": "rubber", "मसाले": "masale", "जौ": "jau", "मटर": "matar",
        "सोयाबीन": "soyabean", "चना": "chana", "गन्ना": "ganna", "आलू": "aloo", "अदरक": "adrak", "तिलहन": "tilhan",
        "बड़ी इलायची": "badi elaichi", "अनानास": "ananas", "तटीय जलोढ़": "coastal alluvial", "जलोढ़": "alluvial",
        "लेटराइट": "laterite", "वन": "forest", "पर्वतीय": "mountain", "लाल-पीली": "red-yellow", "लाल": "red", "काली": "black",
        "रेगिस्तानी": "desert", "लवणीय-क्षारीय": "saline-alkaline", "मूंगा रेत": "coral sand", "तटीय": "coastal", "तराई": "terai",
    }
    # Replace longer phrases first: otherwise the "Apple" rule would turn
    # "Pineapple" into the broken mixed-language text "Pineसेब".
    for source, target in sorted(hindi.items(), key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(source, target)
    if language == "Hinglish":
        for source, target in hinglish.items():
            text = text.replace(source, target)
    return text


def render_farmer_activity_map() -> None:
    """Render the interactive, code-generated India boundary and activity summary."""
    response, error = api_call("GET", "/farmer-activity")
    if error or not response:
        return
    language = st.session_state.get("language", "Hindi")
    title, caption = {
        "Hindi": ("भारत में किसान पहुँच", "सटीक वेक्टर भारत-सीमा • किसी इमेज को चिपकाया नहीं गया • राज्य पर cursor रखें"),
        "Hinglish": ("Bharat mein farmer reach", "Accurate vector India boundary • koi pasted image nahi • state par cursor rakhein"),
        "English": ("Farmer reach across India", "Accurate vector India boundary • not a pasted image • hover over any state"),
    }[language]
    items = response.get("items", [])
    if not isinstance(items, list):
        return
    st.markdown(
        f"""<div style='max-width:1180px;margin:1.4rem auto .65rem;padding:1rem 1.2rem;border:1px solid #cfe3d2;border-left:6px solid #2f8c55;border-radius:16px;background:linear-gradient(100deg,#f4fbf2,#eef7ff);box-shadow:0 8px 22px rgba(34,79,52,.07)'>
        <div style='font-size:.72rem;font-weight:800;letter-spacing:.1em;color:#398352;text-transform:uppercase'>MittiMitra • India farmer insight</div>
        <div style='margin-top:.3rem;font-size:1.35rem;font-weight:800;color:#193b29'>{title}</div>
        <div style='margin-top:.28rem;color:#607568;font-size:.88rem'>{caption}</div></div>""",
        unsafe_allow_html=True,
    )
    map_column, india_summary_column = st.columns([3.45, 1], gap="large")
    with map_column:
        localized_items = [
            {
                **item,
                "key_crops": localize_agriculture_text(item.get("key_crops"), language),
                "common_soils": localize_agriculture_text(item.get("common_soils"), language),
            }
            for item in items
            if isinstance(item, dict)
        ]
        map_status = {
            "Hindi": "वेक्टर भारत मैप • राज्य पर hover करके जानकारी देखें",
            "Hinglish": "Vector India map • state par hover karke details dekhein",
            "English": "Vector India map • hover over a state for details",
        }[language]
        INDIA_ACTIVITY_MAP(
            key="mittimitra_farmer_activity_map",
            data={"items": localized_items, "status": map_status},
            height=650,
        )
    with india_summary_column:
        total_pm_kisan = sum(int(item.get("pm_kisan_beneficiaries", 0)) for item in items if isinstance(item, dict))
        total_active = sum(int(item.get("active_farmers", 0)) for item in items if isinstance(item, dict))
        summary_title = {"Hindi": "पूरे भारत का सार", "Hinglish": "All India summary", "English": "All India summary"}[language]
        st.markdown(f"#### {summary_title}")
        summary_labels = {
            "Hindi": ("विवरण", "भारत", ["PM-KISAN", "सक्रिय MittiMitra किसान", "कृषि GVA", "मुख्य फसलें", "मिट्टी के प्रकार"], [f"{total_pm_kisan:,}", f"{total_active:,}", "17.8%", "अनाज, फल और सब्जियाँ", "जलोढ़, काली, लाल, लेटराइट"]),
            "Hinglish": ("Detail", "Bharat", ["PM-KISAN", "Active MittiMitra farmers", "Agriculture GVA", "Key crops", "Soil types"], [f"{total_pm_kisan:,}", f"{total_active:,}", "17.8%", "Anaaj, phal aur sabziyan", "Alluvial, kaali, laal, laterite"]),
            "English": ("Detail", "India", ["PM-KISAN", "Active MittiMitra farmers", "Agriculture GVA", "Key crops", "Soil types"], [f"{total_pm_kisan:,}", f"{total_active:,}", "17.8%", "Cereals, fruits & vegetables", "Alluvial, black, red, laterite"]),
        }[language]
        st.table({summary_labels[0]: summary_labels[2], summary_labels[1]: summary_labels[3]})
        st.caption("PM-KISAN: 20th instalment snapshot • 04 Aug 2025")


def dashboard() -> None:
    render_language_control()
    header, profile_action, action = st.columns([4.3, 1.6, 1])
    with header:
        st.markdown('<div class="brand">Mitti<span>Mitra</span></div>', unsafe_allow_html=True)
    with profile_action:
        render_profile_corner()
    with action:
        if st.button(tr("sign_out"), width="stretch"):
            st.session_state.logged_in = False
            st.session_state.pop("session_token", None)
            st.session_state.pop("farmer_state", None)
            st.session_state.pop("show_registration", None)
            st.rerun()

    st.markdown(
        f"""<section class="hero"><div class="eyebrow">{tr('hello')}, {st.session_state.user_name} • {tr('soil_intelligence')}</div><h1>{tr('dashboard_title')}</h1><p>{tr('dashboard_copy')}</p><span class="badge">{tr('camera_badge')}</span></section>""",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='notice'><strong>{tr('prototype_note')}</strong><br>{tr('prototype_copy')}</div>", unsafe_allow_html=True)

    st.markdown(f"<br><div class='eyebrow'>{tr('analyse')}</div>", unsafe_allow_html=True)
    with st.container(border=True):
        upload_column, instant_result_column = st.columns([1.08, .92], gap="large")
        with upload_column:
            upload = st.file_uploader(tr("upload"), type=["jpg", "jpeg", "png", "webp"])
            if upload:
                st.image(upload, caption=tr("preview"), use_container_width=True)
            run_prediction = st.button(tr("run"), use_container_width=True, disabled=upload is None)
            st.caption(tr("input_hint"))
        with instant_result_column:
            st.markdown(f"#### {tr('profile')}")
            st.caption(instant_result_text("waiting"))
            instant_result_slot = st.empty()

    if upload and run_prediction:
        with st.spinner(tr("reading")):
            result_response, error = api_call(
                "POST",
                "/samples",
                headers={"X-Session-Token": st.session_state.get("session_token", "")},
                files={"image": (upload.name, upload.getvalue(), upload.type or "image/jpeg")},
            )
        if error:
            st.error(error)
            return
        result = result_response["prediction"]
        sample_id = result_response["sample_id"]
        levels = result["recommendation"]["levels"]
        with instant_result_slot.container():
            st.success(instant_result_text("ready"))
            instant_cards = (
                (tr("nitrogen"), result["nitrogen_kg_ha"], "kg/ha"),
                (tr("phosphorus"), result["phosphorus_kg_ha"], "kg/ha"),
                (tr("potassium"), result["potassium_kg_ha"], "kg/ha"),
                (tr("moisture"), result["moisture_percent"] or 0, "%"),
            )
            for column, (label, value, unit) in zip(st.columns(2), instant_cards):
                with column:
                    st.metric(label, f"{value:.1f} {unit}")
            st.caption(instant_result_text("detail"))
        st.success("Photo safely save ho gayi aur prediction run ho gaya. Lab report add karne par yeh future retraining ke liye eligible hogi.")
        st.markdown(f"<br><div class='eyebrow'>{tr('profile')}</div>", unsafe_allow_html=True)
        cards = ((tr("nitrogen"), result["nitrogen_kg_ha"], localized_status(levels["nitrogen"]), "kg/ha"), (tr("phosphorus"), result["phosphorus_kg_ha"], localized_status(levels["phosphorus"]), "kg/ha"), (tr("potassium"), result["potassium_kg_ha"], localized_status(levels["potassium"]), "kg/ha"), (tr("moisture"), result["moisture_percent"] or 0, localized_status(result["recommendation"]["water_status"]), "%"))
        for column, (label, value, status, unit) in zip(st.columns(4), cards):
            with column:
                st.markdown(nutrient_card(label, value, status, unit), unsafe_allow_html=True)
        st.markdown(f"<br><div class='notice'><strong>{tr('next_step')}</strong><br>" + "<br>".join(localized_actions(levels)) + "</div>", unsafe_allow_html=True)
        crops, method = st.columns([1, 1.4], gap="large")
        with crops:
            st.markdown(f"#### {tr('crop_match')}")
            st.caption(tr("crop_hint"))
            for crop in result["recommendation"]["crop_suggestions"]:
                st.write(f"• {localized_crop(crop)}")
        with method:
            st.markdown(f"#### {tr('method')}")
            principle = result["estimate_principle"]
            language = language_mode()
            if language == "Hindi":
                st.write("फोटो → रंग और सतह की बनावट → सिंथेटिक उदाहरणों से तुलना → NPK व नमी का शुरुआती अनुमान")
                st.caption(f"मॉडल ने औसत RGB {principle['signals']['average_rgb']} और बनावट में अंतर {principle['signals']['texture_variation']} का उपयोग किया।")
            elif language == "Hinglish":
                st.write("Photo → colour aur texture → synthetic examples se comparison → NPK aur moisture ka initial estimate")
                st.caption(f"Model ne average RGB {principle['signals']['average_rgb']} aur texture variation {principle['signals']['texture_variation']} use kiya.")
            else:
                st.write("Photo → colour and texture → comparison with synthetic examples → initial NPK and moisture estimate")
                st.caption(f"The model used average RGB {principle['signals']['average_rgb']} and texture variation {principle['signals']['texture_variation']}.")
            st.caption(tr("method_note"))
        with st.expander("Certified lab report add karein (model training ke liye)"):
            st.caption("Sirf certified soil-lab values hi save karein. Photo ke prediction ko lab result maan kar submit na karein.")
            with st.form(f"lab_result_{sample_id}"):
                lab_n, lab_p, lab_k = st.columns(3)
                with lab_n:
                    nitrogen = st.number_input("Lab Nitrogen (kg/ha)", min_value=0.0, value=0.0, key=f"n_{sample_id}")
                with lab_p:
                    phosphorus = st.number_input("Lab Phosphorus (kg/ha)", min_value=0.0, value=0.0, key=f"p_{sample_id}")
                with lab_k:
                    potassium = st.number_input("Lab Potassium (kg/ha)", min_value=0.0, value=0.0, key=f"k_{sample_id}")
                submit_lab = st.form_submit_button("Lab result save karein aur auto-training check karein")
            if submit_lab:
                training_response, training_error = api_call(
                    "POST", f"/samples/{sample_id}/lab-results",
                    headers={"X-Session-Token": st.session_state.get("session_token", "")},
                    json={"nitrogen_kg_ha": nitrogen, "phosphorus_kg_ha": phosphorus, "potassium_kg_ha": potassium},
                )
                if training_error:
                    st.error(training_error)
                elif training_response:
                    training = training_response["training"]
                    if training["status"] == "retrained":
                        st.success(f"Model automatically retrain ho gaya ({training['labeled_samples']} verified samples).")
                    else:
                        st.info(f"Lab result save ho gaya. Auto-training {training['minimum_required']} verified samples par chalegi; abhi {training['labeled_samples']} hain.")
    st.markdown("<br>", unsafe_allow_html=True)
    render_account_and_lab_tools()
    st.markdown("<br>", unsafe_allow_html=True)
    render_kisan_mitra_floating()
    render_farmer_activity_map()
    if not (upload and run_prediction):
        st.markdown("<br>", unsafe_allow_html=True)
        render_state_resources()


inject_css()
if "language" not in st.session_state:
    st.session_state.language = "Hindi"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if st.session_state.get("admin_mode"):
    if st.session_state.get("admin_authenticated"):
        admin_dashboard()
    else:
        admin_login_screen()
elif st.session_state.logged_in:
    dashboard()
else:
    login_screen()
