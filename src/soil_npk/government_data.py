"""Small, auditable government data snapshots used for dashboard context.

These figures are never used to represent MittiMitra registrations or eligibility.
"""

# PM-KISAN 20th instalment: beneficiaries covered as on 04 August 2025.
# Source: Lok Sabha Unstarred Question 4271, answered 19 August 2025,
# Statement on pages 581-582 of the official parliamentary record.
PM_KISAN_20TH_INSTALLMENT_AS_OF = "2025-08-04"
PM_KISAN_20TH_INSTALLMENT_SOURCE = "https://eparlib.sansad.in/bitstream/123456789/2992956/1/lsd_18_V_19-08-2025.pdf"
PM_KISAN_20TH_INSTALLMENT_BENEFICIARIES = {
    "Andaman and Nicobar Islands": 13159, "Andhra Pradesh": 4006453, "Arunachal Pradesh": 88292,
    "Assam": 1933783, "Bihar": 7365327, "Chandigarh": 0, "Chhattisgarh": 2517925,
    "Dadra and Nagar Haveli and Daman and Diu": 11808, "Delhi": 11516, "Goa": 6296,
    "Gujarat": 5138305, "Haryana": 1609832, "Himachal Pradesh": 829996, "Jammu and Kashmir": 873673,
    "Jharkhand": 1889647, "Karnataka": 4329135, "Kerala": 2889822, "Ladakh": 17931,
    "Lakshadweep": 2313, "Madhya Pradesh": 8301722, "Maharashtra": 9205501, "Manipur": 74094,
    "Meghalaya": 179617, "Mizoram": 128014, "Nagaland": 188784, "Odisha": 3465575,
    "Puducherry": 5538, "Punjab": 1134567, "Rajasthan": 7179664, "Sikkim": 31328,
    "Tamil Nadu": 2224726, "Telangana": 3048771, "Tripura": 215587, "Uttar Pradesh": 22917063,
    "Uttarakhand": 819201, "West Bengal": 4478537,
}

# Compact, farmer-facing profiles. "Key crops" and "common soils" are broad
# state/UT indicators, not a substitute for district-level crop/soil surveys.
# Sources: DES crop statistics and Economic Survey soil-type table.
STATE_AGRI_PROFILES = {
    "Andaman and Nicobar Islands": ("Coconut, arecanut, rice", "Coastal alluvial, laterite"),
    "Andhra Pradesh": ("Rice, cotton, chilli", "Red, black, coastal alluvial"),
    "Arunachal Pradesh": ("Rice, maize, millets", "Forest, mountain, alluvial"),
    "Assam": ("Rice, tea, jute", "Alluvial, red, laterite"), "Bihar": ("Rice, wheat, maize", "Alluvial"),
    "Chandigarh": ("Wheat, rice, vegetables", "Alluvial"), "Chhattisgarh": ("Rice, maize, pulses", "Red-yellow, laterite, alluvial"),
    "Dadra and Nagar Haveli and Daman and Diu": ("Rice, mango, coconut", "Alluvial, laterite"),
    "Delhi": ("Wheat, vegetables, mustard", "Alluvial"), "Goa": ("Rice, cashew, coconut", "Laterite, coastal alluvial"),
    "Gujarat": ("Cotton, groundnut, bajra", "Black, alluvial, desert"), "Haryana": ("Wheat, rice, mustard", "Alluvial, saline-alkaline"),
    "Himachal Pradesh": ("Apple, maize, wheat", "Mountain, forest, alluvial"), "Jammu and Kashmir": ("Apple, rice, maize", "Mountain, alluvial, forest"),
    "Jharkhand": ("Rice, maize, pulses", "Red-yellow, laterite"), "Karnataka": ("Ragi, maize, coffee", "Red, black, laterite"),
    "Kerala": ("Coconut, rubber, spices", "Laterite, coastal alluvial"), "Ladakh": ("Barley, wheat, peas", "Mountain, desert"),
    "Lakshadweep": ("Coconut", "Coral sand, coastal"), "Madhya Pradesh": ("Soybean, wheat, gram", "Black, red-yellow, alluvial"),
    "Maharashtra": ("Cotton, soybean, sugarcane", "Black, red, laterite"), "Manipur": ("Rice, maize, pulses", "Alluvial, red, forest"),
    "Meghalaya": ("Rice, maize, potato", "Red, laterite, forest"), "Mizoram": ("Rice, maize, ginger", "Red, laterite, forest"),
    "Nagaland": ("Rice, maize, pulses", "Red, forest, mountain"), "Odisha": ("Rice, pulses, oilseeds", "Red, laterite, coastal alluvial"),
    "Puducherry": ("Rice, sugarcane, coconut", "Alluvial, red, coastal"), "Punjab": ("Wheat, rice, cotton", "Alluvial"),
    "Rajasthan": ("Bajra, wheat, mustard", "Desert, alluvial, black"), "Sikkim": ("Large cardamom, maize, rice", "Mountain, forest"),
    "Tamil Nadu": ("Rice, sugarcane, cotton", "Red, black, alluvial"), "Telangana": ("Rice, cotton, maize", "Red, black"),
    "Tripura": ("Rice, rubber, pineapple", "Red, laterite, alluvial"), "Uttar Pradesh": ("Wheat, rice, sugarcane", "Alluvial, terai"),
    "Uttarakhand": ("Rice, wheat, millets", "Mountain, forest, alluvial"), "West Bengal": ("Rice, jute, potato", "Alluvial, laterite, coastal"),
}

# Agriculture and allied sector share of total State GSVA at current prices,
# 2023-24. "None" is the official data-unavailable status, not a zero value.
AGRICULTURE_GSVA_SHARE_2023_24 = {
    "Andaman and Nicobar Islands": 11.74, "Andhra Pradesh": 34.08, "Arunachal Pradesh": 24.35,
    "Assam": 21.31, "Bihar": 23.90, "Chandigarh": 0.59, "Chhattisgarh": 20.34,
    "Dadra and Nagar Haveli and Daman and Diu": None, "Delhi": 0.28, "Goa": 6.26,
    "Gujarat": 16.15, "Haryana": 17.90, "Himachal Pradesh": 14.27, "Jammu and Kashmir": 19.24,
    "Jharkhand": 15.72, "Karnataka": 11.95, "Kerala": 9.26, "Ladakh": None,
    "Lakshadweep": None, "Madhya Pradesh": 41.30, "Maharashtra": 11.25, "Manipur": 21.28,
    "Meghalaya": 23.05, "Mizoram": 17.14, "Nagaland": 27.14, "Odisha": 19.15,
    "Puducherry": 5.07, "Punjab": 24.95, "Rajasthan": 26.78, "Sikkim": 8.15,
    "Tamil Nadu": 12.69, "Telangana": 15.54, "Tripura": 37.64, "Uttar Pradesh": 25.80,
    "Uttarakhand": 8.60, "West Bengal": 20.73,
}
AGRICULTURE_GSVA_SHARE_SOURCE = "https://desagri.gov.in/wp-content/uploads/2024/11/Agricultural-Statisitcs-at-a-Glance-2024-25_%E0%A4%95%E0%A5%83%E0%A4%B7%E0%A4%BF-%E0%A4%B8%E0%A4%BE%E0%A4%82%E0%A4%96%E0%A5%8D%E0%A4%AF%E0%A4%BF%E0%A4%95%E0%A5%80-%E0%A4%8F%E0%A4%95-%E0%A4%9D%E0%A4%B2%E0%A4%95-2024%E2%80%9325.pdf"
