"""Deterministic calculators. Numbers from the rulebook tables live here, in code,
never in a language model's head. Every table is transcribed from the official
English PDF and carries its rule, sub-rule and page so the answer can cite it."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

HIGH_RISE_M = 30.0  # Rule 2: high-rise means height above 30 m (or > 10 storeys)
LOW_RISE_LIMIT_M = 12.5  # Rule 56 tables apply up to 12.5 m height

# Rule 56(1)(a), PDF p.77: width of street facing the plot -> min front open space
FRONT_TABLE = [  # (upper bound of street width inclusive, front open space m, row label)
    (9.0, 3.0, "Up to 9.0 meters"),
    (12.0, 3.6, "More than 9.0 meters and up to 12 meters"),
    (18.0, 4.5, "More than 12.0 meters and up to 18 meters"),
    (float("inf"), 6.0, "Above 18 meters"),
]

# Rule 56(2)(a), PDF p.78: plot area -> min rear open space
REAR_TABLE = [
    (40.0, 0.0, "Up to 40.00"),
    (150.0, 1.5, "Above 40.00 and up to 150.00"),
    (225.0, 2.5, "Above 150 and up to 225.00"),
    (float("inf"), 3.0, "Above 225.00"),
]

# Rule 21(3)(b) item 1, PDF p.36: residential built-up area slabs -> permission fee (Rs)
FEE_SLABS = [
    (75, 750), (125, 1250), (200, 2000), (300, 3000), (400, 4000), (600, 6000), (750, 7500),
    (1000, 10000), (1250, 12500), (1500, 15000), (2000, 20000), (2500, 25000), (float("inf"), 50000),
]

USE_MULTIPLIER_LOW = {  # Rule 21(3)(b) items 1-4, 6
    "residential": (1.0, "item 1"),
    "commercial": (1.5, "item 2 (item 1 + 50%)"),
    "industrial": (1.5, "item 2 (item 1 + 50%)"),
    "factory_admin": (1.0, "item 3"),
    "shop_cum_residence": (1.5, "item 4 (item 1 + 50%)"),
    "institutional": (1.0, "item 6 (same as item 1)"),
}
USE_MULTIPLIER_HIGH = {  # Rule 21(3)(c) high-rise: Rs 10 per sq m base
    "residential": (1.0, "item 1"),
    "commercial": (2.0, "item 2 (item 1 + 100%)"),
    "industrial": (2.0, "item 2 (item 1 + 100%)"),
    "factory_admin": (1.0, "item 3"),
    "shop_cum_residence": (1.5, "item 4 (item 1 + 50%)"),
    "institutional": (1.0, "item 5"),
}


@dataclass
class CalcResult:
    tool: str
    value: float | None
    unit: str
    explanation: str
    explanation_hi: str
    rule: str
    sub_rule: str
    page: int
    table_row: str = ""
    inputs: dict | None = None
    warnings: list[str] | None = None

    def dict(self) -> dict:
        return asdict(self)


def front_open_space(street_width_m: float, height_m: float | None = None) -> CalcResult:
    warnings = []
    if height_m is not None and height_m > LOW_RISE_LIMIT_M:
        return CalcResult(
            "front_open_space", None, "m",
            f"Building height {height_m} m is above 12.5 m, so Rule 56(1) does not apply. Rule 56(5) sends you to Table 4 and 5 of Rule 42.",
            f"भवन की ऊँचाई {height_m} मीटर, 12.5 मीटर से अधिक है, इसलिए नियम 56(1) लागू नहीं होता। नियम 56(5) के अनुसार नियम 42 की तालिका 4 और 5 देखें।",
            "56", "56(5) → 42 Table 4/5", 77, inputs={"street_width_m": street_width_m, "height_m": height_m},
        )
    for upper, value, label in FRONT_TABLE:
        if street_width_m <= upper:
            if street_width_m < 6.0:
                warnings.append("Street under 6 m in an existing developed area: Rule 56(1)(b) puts the building line 6.0 m from the street centre line.")
            return CalcResult(
                "front_open_space", value, "m",
                f"A residential building up to 12.5 m tall facing a {street_width_m:g} m street falls in the row \"{label}\", so the minimum front open space is {value} m.",
                f"12.5 मीटर तक ऊँचे आवासीय भवन के सामने {street_width_m:g} मीटर चौड़ी सड़क \"{label}\" वाली पंक्ति में आती है, इसलिए आगे कम से कम {value} मीटर खुली जगह छोड़नी होगी।",
                "56", "56(1)(a)", 77, label, {"street_width_m": street_width_m, "height_m": height_m}, warnings or None,
            )
    raise ValueError("unreachable")


def rear_open_space(plot_area_sqm: float, height_m: float | None = None) -> CalcResult:
    if height_m is not None and height_m > LOW_RISE_LIMIT_M:
        return CalcResult(
            "rear_open_space", None, "m",
            "Above 12.5 m height, open spaces come from Rule 42 Table 4/5 (Rule 56(5)).",
            "12.5 मीटर से ऊँचे भवन के लिए खुली जगह नियम 42 की तालिका 4/5 से तय होती है (नियम 56(5))।",
            "56", "56(5)", 78, inputs={"plot_area_sqm": plot_area_sqm, "height_m": height_m},
        )
    for upper, value, label in REAR_TABLE:
        if plot_area_sqm <= upper:
            v = "Nil" if value == 0 else f"{value} m"
            v_hi = "शून्य" if value == 0 else f"{value} मीटर"
            return CalcResult(
                "rear_open_space", value, "m",
                f"A {plot_area_sqm:g} sq m residential plot (building up to 12.5 m) falls in the row \"{label}\", so the minimum rear open space is {v}.",
                f"{plot_area_sqm:g} वर्ग मीटर का आवासीय प्लॉट \"{label}\" पंक्ति में आता है, इसलिए पीछे कम से कम {v_hi} खुली जगह चाहिए।",
                "56", "56(2)(a)", 78, label, {"plot_area_sqm": plot_area_sqm, "height_m": height_m},
            )
    raise ValueError("unreachable")


def building_permission_fee(built_up_sqm: float, use: str = "residential", height_m: float | None = None) -> CalcResult:
    use = use if use in USE_MULTIPLIER_LOW else "residential"
    application_fee = round(built_up_sqm * 1.0, 2)  # Rule 21(2)(ii): Rs 1.00 per sq m
    high_rise = height_m is not None and height_m > HIGH_RISE_M
    if high_rise:
        mult, item = USE_MULTIPLIER_HIGH[use]
        permission = round(built_up_sqm * 10.0 * mult, 2)
        sub, page, row = f"21(3)(c) {item}", 37, "Rs 10.00 per sq m of built-up area"
    else:
        mult, item = USE_MULTIPLIER_LOW[use]
        base = next(fee for upper, fee in FEE_SLABS if built_up_sqm <= upper)
        permission = round(base * mult, 2)
        lo = 0
        for upper, fee in FEE_SLABS:
            if built_up_sqm <= upper:
                row = f"{lo}-{upper if upper != float('inf') else '∞'} sq m → Rs {fee:,}"
                break
            lo = int(upper) + 1
        sub, page = f"21(3)(b) {item}", 36
    total = application_fee + permission
    return CalcResult(
        "building_permission_fee", total, "INR",
        f"Application fee Rs {application_fee:,.0f} (Rule 21(2)(ii): Rs 1 per sq m of {built_up_sqm:g} sq m) + permission fee Rs {permission:,.0f} (Rule {sub}) = Rs {total:,.0f}.",
        f"आवेदन शुल्क ₹{application_fee:,.0f} (नियम 21(2)(ii): ₹1 प्रति वर्ग मीटर) + अनुमति शुल्क ₹{permission:,.0f} (नियम {sub}) = कुल ₹{total:,.0f}।",
        "21", sub, page, row,
        {"built_up_sqm": built_up_sqm, "use": use, "height_m": height_m, "application_fee": application_fee, "permission_fee": permission},
        ["Permission fee must be deposited within 15 days of intimation (Rule 21(3)(d))."],
    )


# ---------------- parameter extraction from free text ----------------
NUM = r"(\d+(?:\.\d+)?)"


def extract_params(text: str) -> dict:
    t = text.lower().replace("sq.m", "sq m").replace("sqm", "sq m").replace("square meter", "sq m").replace("square metre", "sq m")
    t = t.replace("वर्ग मीटर", "sq m").replace("मीटर", "m").replace("मी.", "m")
    p: dict = {}
    m = re.search(NUM + r"\s*(?:sq\s*m|sq\.? ?mt|sq\.? ?ft)", t)
    if m:
        p["area_sqm"] = float(m.group(1))
    m = re.search(NUM + r"\s*m(?:eters?|etres?|tr)?\s*(?:wide|width|चौड़ी|चौड़ाई)?\s*(?:road|street|सड़क|सडक|rasta)", t) or \
        re.search(r"(?:road|street|सड़क)\s*(?:of|is|width)?\s*" + NUM + r"\s*m", t) or \
        re.search(NUM + r"\s*m\s*(?:wide|चौड़ी)", t)
    if m:
        p["street_width_m"] = float(m.group(1))
    m = re.search(NUM + r"\s*m(?:eters?|etres?)?\s*(?:tall|high|height|ऊँचा|ऊंचा|ऊँचाई|ऊंचाई)", t) or \
        re.search(r"(?:height|taller than|ऊँचाई|ऊंचाई)\s*(?:of|is)?\s*" + NUM + r"\s*m", t)
    if m:
        p["height_m"] = float(m.group(1))
    if re.search(r"shop|commercial|दुकान|व्यावसायिक", t):
        p["use"] = "shop_cum_residence" if re.search(r"residen|आवास|मकान", t) else "commercial"
    return p


def plan_tools(text_en: str, text_orig: str) -> list[CalcResult]:
    """Decide which calculators a question needs (the 'tool-use' step of the agent)."""
    p = extract_params(text_orig + " " + text_en)
    q = (text_en + " " + text_orig).lower()
    out: list[CalcResult] = []
    asks_front = re.search(r"front|आगे|सामने", q) and re.search(r"open|space|gap|setback|खाली|जगह", q)
    asks_rear = re.search(r"rear|back|पीछे", q) and re.search(r"open|space|gap|setback|खाली|जगह", q)
    asks_fee = re.search(r"\bfee|fees|charge|शुल्क|फीस", q)
    if asks_front and "street_width_m" in p:
        out.append(front_open_space(p["street_width_m"], p.get("height_m")))
    if asks_rear and "area_sqm" in p:
        out.append(rear_open_space(p["area_sqm"], p.get("height_m")))
    if asks_fee and "area_sqm" in p:
        out.append(building_permission_fee(p["area_sqm"], p.get("use", "residential"), p.get("height_m")))
    elif asks_fee and re.search(r"building|बिल्डिंग|भवन|house|मकान|residential", q):
        out.append(fee_schedule())
    return out


def fee_schedule() -> CalcResult:
    """No area given: return the whole residential schedule so the clerk can read the slab."""
    slabs, lo = [], 0
    for upper, fee in FEE_SLABS:
        slabs.append(f"{lo}-{int(upper)} sq m: Rs {fee:,}" if upper != float("inf") else f"above 2500 sq m: Rs {fee:,}")
        lo = int(upper) + 1 if upper != float("inf") else lo
    return CalcResult(
        "fee_schedule", None, "INR",
        "Building permission for a residential house costs an application fee of Rs 1 per sq m of built-up area (Rule 21(2)(ii)) plus a permission fee by built-up area slab (Rule 21(3)(b) item 1): from Rs 750 (up to 75 sq m) to Rs 50,000 (above 2,500 sq m). High-rise buildings pay Rs 10 per sq m (Rule 21(3)(c)). Tell me the built-up area for the exact amount.",
        "आवासीय भवन की बिल्डिंग परमिशन फीस: आवेदन शुल्क ₹1 प्रति वर्ग मीटर निर्मित क्षेत्र (नियम 21(2)(ii)) और निर्मित क्षेत्र के स्लैब के अनुसार अनुमति शुल्क (नियम 21(3)(b) मद 1): ₹750 (75 वर्ग मीटर तक) से ₹50,000 (2,500 वर्ग मीटर से अधिक) तक। ऊँचे भवन (हाई-राइज़) के लिए ₹10 प्रति वर्ग मीटर (नियम 21(3)(c))। सटीक राशि के लिए निर्मित क्षेत्र बताएं।",
        "21", "21(2)(ii), 21(3)(b) item 1", 36, "; ".join(slabs), {}, None,
    )
