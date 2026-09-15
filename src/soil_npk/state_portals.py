"""Verified public agriculture-department portals for India's 28 states.

URLs are sourced from APEDA Farmer Connect's state/UT agriculture links and
updated to current official department landing pages when a legacy link fails.
Keep them in one place so a future app can refresh or validate them independently.
"""

STATE_PORTALS = {
    "Andhra Pradesh": ("Agriculture Department, Andhra Pradesh", "https://www.apagrisnet.gov.in/APPRPortal/"),
    "Arunachal Pradesh": ("Department of Agriculture, Arunachal Pradesh", "http://www.agri.arunachal.gov.in/"),
    "Assam": ("Agriculture & Horticulture Department, Assam", "https://agri-horti.assam.gov.in/"),
    "Bihar": ("Agriculture Department / DBT Agriculture, Bihar", "https://dbtagriculture.bihar.gov.in/"),
    "Chhattisgarh": ("Agriculture Development & Farmers Welfare, Chhattisgarh", "https://agriwelfare.gov.in/"),
    "Goa": ("Directorate of Agriculture, Goa", "http://agri.goa.gov.in"),
    "Gujarat": ("Agriculture, Farmers Welfare & Co-operation, Gujarat", "https://agri.gujarat.gov.in/"),
    "Haryana": ("Agriculture & Farmers Welfare, Haryana", "https://agriharyana.gov.in/"),
    "Himachal Pradesh": ("Department of Agriculture, Himachal Pradesh", "https://agriculture.hp.gov.in/en/home-english/"),
    "Jharkhand": ("Agriculture, Animal Husbandry & Cooperative, Jharkhand", "https://www.jharkhand.gov.in/agriculture"),
    "Karnataka": ("Karnataka Agriculture Department", "https://karnataka.mygov.in/en"),
    "Kerala": ("Agriculture Development & Farmers Welfare, Kerala", "http://www.keralaagriculture.gov.in/"),
    "Madhya Pradesh": ("Farmer Welfare & Agriculture Development, Madhya Pradesh", "https://farmer.mpdage.mp.gov.in/"),
    "Maharashtra": ("Department of Agriculture, Maharashtra", "http://krishi.maharashtra.gov.in"),
    "Manipur": ("Department of Agriculture, Manipur", "https://agrimanipur.mn.gov.in/"),
    "Meghalaya": ("Department of Agriculture, Meghalaya", "https://megagriculture.gov.in/"),
    "Mizoram": ("Directorate of Agriculture, Mizoram", "http://agriculturemizoram.nic.in/"),
    "Nagaland": ("Department of Agriculture, Nagaland", "https://agriculture.nagaland.gov.in/"),
    "Odisha": ("Agriculture & Farmers' Empowerment, Odisha", "https://agri.odisha.gov.in/en/"),
    "Punjab": ("Agriculture & Farmer Welfare, Punjab", "https://agri.punjab.gov.in/"),
    "Rajasthan": ("Department of Agriculture, Rajasthan", "https://agriculture.rajasthan.gov.in/home"),
    "Sikkim": ("Department of Agriculture, Sikkim", "https://agri.sikkim.gov.in/"),
    "Tamil Nadu": ("Department of Agriculture, Tamil Nadu", "https://www.tnagrisnet.tn.gov.in/"),
    "Telangana": ("Department of Agriculture, Telangana", "http://agri.telangana.gov.in/"),
    "Tripura": ("Agriculture & Farmers Welfare, Tripura", "https://agri.tripura.gov.in/"),
    "Uttar Pradesh": ("Agriculture Department, Uttar Pradesh", "https://agriculture.up.gov.in/"),
    "Uttarakhand": ("Agriculture Department, Uttarakhand", "http://agriculture.uk.gov.in/"),
    "West Bengal": ("Department of Agriculture, West Bengal", "https://agriculture.wb.gov.in/"),
}

# Two additional farmer-facing official resources per state. Together with the
# department portal above, the dashboard presents three useful links per state.
STATE_EXTRA_RESOURCES = {
    "Andhra Pradesh": (("Horticulture Department", "https://horticulturedept.ap.gov.in/Horticulture/Newhome.aspx"), ("Agricultural Marketing", "http://market.ap.nic.in/")),
    "Arunachal Pradesh": (("Arunachal Horticulture", "https://arunachalpradesh.gov.in/"), ("State Government Portal", "https://arunachalpradesh.gov.in/")),
    "Assam": (("Agricultural Marketing Board", "https://asamb.assam.gov.in/"), ("Assam Government Portal", "https://assam.gov.in/")),
    "Bihar": (("Directorate of Horticulture", "https://horticulture.bihar.gov.in/"), ("Bihar Government Services", "https://serviceonline.bihar.gov.in/")),
    "Chhattisgarh": (("Horticulture & Farm Forestry", "https://agriportal.cg.nic.in/horticulture/HortiEn/Default.aspx"), ("Agricultural Marketing Board", "https://services.india.gov.in/service/detail/chhattisgarh-state-agricultural-marketing-board")),
    "Goa": (("Goa Agricultural Marketing Board", "http://gsamb.in/"), ("Goa Government Portal", "https://www.goa.gov.in/")),
    "Gujarat": (("Directorate of Horticulture", "https://doh.gujarat.gov.in/Index"), ("iKhedut Farmer Services", "https://ikhedut.gujarat.gov.in/")),
    "Haryana": (("Meri Fasal Mera Byora", "https://fasal.haryana.gov.in/"), ("SARAL Haryana", "https://saralharyana.gov.in/")),
    "Himachal Pradesh": (("Himachal Horticulture", "https://eudyan.hp.gov.in/cms/en/index"), ("Agricultural Marketing Board", "https://hpsamb.org/")),
    "Jharkhand": (("Jharkhand Horticulture", "http://horticulturejharkhand.org/"), ("Jharkhand Government Portal", "https://www.jharkhand.gov.in/")),
    "Karnataka": (("Karnataka Horticulture", "https://www.karnataka.gov.in/horticulture/Pages/home.aspx"), ("Raita Mitra Farmer Services", "https://raitamitra.karnataka.gov.in/")),
    "Kerala": (("Kerala Agriculture Services", "https://www.keralaagriculture.gov.in/"), ("Kerala Government Portal", "https://kerala.gov.in/")),
    "Madhya Pradesh": (("Madhya Pradesh Horticulture", "http://www.mphorticulture.gov.in/en"), ("MP e-Mandi", "https://eanugya.mp.gov.in/eMandi/Home/Home.html")),
    "Maharashtra": (("Agricultural Marketing Board", "https://www.msamb.com/"), ("MahaDBT Farmer Services", "https://mahadbt.maharashtra.gov.in/")),
    "Manipur": (("Manipur Horticulture", "http://www.horticulture.mn.gov.in/"), ("Manipur Government Portal", "https://manipur.gov.in/")),
    "Meghalaya": (("Meghalaya Farmer Portal", "https://www.megfarmer.gov.in/"), ("Agricultural Marketing Board", "http://megamb.gov.in/")),
    "Mizoram": (("Mizoram Horticulture", "https://horticulture.mizoram.gov.in/"), ("Mizoram Agricultural Marketing", "https://mamco.mizoram.gov.in/")),
    "Nagaland": (("Nagaland Horticulture", "https://hortidept.nagaland.gov.in/"), ("Nagaland Government Portal", "https://nagaland.gov.in/")),
    "Odisha": (("GO SUGAM Farmer Services", "https://sugam.odisha.gov.in/"), ("Odisha AGRISNET", "https://agrisnetodisha.ori.nic.in/")),
    "Punjab": (("Punjab Horticulture", "https://punjabhorticulture.com/"), ("Punjab e-Mandi", "https://emandikaran-pb.in/")),
    "Rajasthan": (("Agricultural Marketing Board", "https://agriculture.rajasthan.gov.in/rsamb/#/home/dptHome"), ("Rajasthan Government Services", "https://sso.rajasthan.gov.in/")),
    "Sikkim": (("Sikkim Agriculture Services", "https://agri.sikkim.gov.in/"), ("NERAMAC", "https://www.neramac.com/about-us/")),
    "Tamil Nadu": (("Tamil Nadu Horticulture", "https://tnhorticulture.tn.gov.in/"), ("Agricultural Marketing Board", "https://www.agrimark.tn.gov.in/home/tnsamb")),
    "Telangana": (("Telangana Horticulture", "https://horticulture.tg.nic.in/"), ("Agricultural Marketing", "https://tgmarketing.co.in/")),
    "Tripura": (("Tripura Horticulture", "https://horti.tripura.gov.in/"), ("Tripura Government Portal", "https://tripura.gov.in/")),
    "Uttar Pradesh": (("UP Horticulture", "http://uphorticulture.gov.in/"), ("UP Mandi Parishad", "https://upmandiparishad.upsdc.gov.in/")),
    "Uttarakhand": (("Uttarakhand Horticulture", "http://shm.uk.gov.in/"), ("Uttarakhand e-Mandi", "https://emandiuk.in/")),
    "West Bengal": (("West Bengal Horticulture", "https://wbfpih.wb.gov.in/"), ("Agricultural Marketing Board", "https://wbagrimarketingboard.gov.in/")),
}
