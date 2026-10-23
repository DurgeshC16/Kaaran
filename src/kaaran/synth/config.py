"""Generator configuration: talukas, planted-truth numbers, name sets.

All numbers here mirror the tables in docs/SYNTHETIC_DATA_SPEC.md (v2).
Change the spec first, then this file.
"""

from __future__ import annotations

from dataclasses import dataclass

# One-line switch for public demos: "solapur" (real taluka names) or "fictional".
TALUKA_NAMES = "solapur"

DISTRICT_NAME = "SYNTHETIC DEMO DISTRICT"
STATE_PREFIX = "00"  # no real state uses 00, so codes never collide with real UDISE codes
DISTRICT_CODE = "99"

YEARS = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
SCHOOL_MONTHS = (6, 7, 8, 9, 10, 11, 12, 1, 2, 3)  # Jun-Mar
# Seasonal attendance offsets (monsoon Jul-Aug, harvest Oct, Diwali Nov); they sum to 0.
SEASONAL_ATTENDANCE = {6: -0.5, 7: -2.0, 8: -1.5, 9: 0.5, 10: -1.0, 11: -1.5, 12: 1.0, 1: 1.5, 2: 2.0, 3: 1.5}
ATTENDANCE_CAP = 98.0  # only planted T5 schools report above this

SUBJECT = "Maths"
STD = 3

# Roles (internal keys; display names come from the name set).
FOCUS = "pandharpur"
TWIN = "malshiras"
DECOY = "sangola"
DIPPER = "akkalkot"
INFRA_LOW = "karmala"
SPARSE = "mangalvedha"


@dataclass(frozen=True)
class TalukaSpec:
    key: str
    block: str
    n_schools: int
    poverty: float
    election: bool  # heavy election duty in ELECTION_YEAR
    scores: tuple[float, ...]  # taluka target per year (unweighted mean of school means)
    n_vacancy: int = 0  # schools with no maths teacher from VACANCY_START_YEAR


# Pandharpur is a mix of vacancy schools and the rest; its taluka target follows from both.
FOCUS_BASE = 56.0
VACANCY_PATTERN = (0.0, 0.0, -4.0, -22.0, -28.0)  # change vs 2021-22 (missed 1, 2, 3 years of maths)
FOCUS_OTHERS_PATTERN = (0.0, -0.1, -0.3, -1.0, -1.2)
FOCUS_SCHOOLS = 140
FOCUS_VACANCY = 11
VACANCY_START_YEAR = "2023-24"


def _focus_scores() -> tuple[float, ...]:
    rest = FOCUS_SCHOOLS - FOCUS_VACANCY
    return tuple(
        FOCUS_BASE + (rest * o + FOCUS_VACANCY * v) / FOCUS_SCHOOLS
        for o, v in zip(FOCUS_OTHERS_PATTERN, VACANCY_PATTERN)
    )


TALUKAS = (
    TalukaSpec("akkalkot", "01", 117, 0.52, True, (53.5, 54.3, 55.2, 53.7, 54.1)),
    TalukaSpec("barshi", "02", 121, 0.40, True, (58.2, 58.9, 59.7, 60.3, 61.2)),
    TalukaSpec("karmala", "03", 116, 0.50, False, (52.0, 52.9, 52.3, 52.9, 52.0), n_vacancy=2),
    TalukaSpec("madha", "04", 118, 0.38, True, (56.5, 57.3, 57.8, 58.5, 59.0)),
    TalukaSpec("malshiras", "05", 134, 0.45, True, (54.0, 55.3, 57.4, 58.2, 60.5)),
    TalukaSpec("mangalvedha", "06", 100, 0.58, False, (52.4, 52.6, 53.1, 52.6, 52.4)),
    TalukaSpec("mohol", "07", 108, 0.35, True, (54.6, 54.9, 56.2, 55.4, 56.4)),
    TalukaSpec("pandharpur", "08", FOCUS_SCHOOLS, 0.42, True, _focus_scores(), n_vacancy=FOCUS_VACANCY),
    TalukaSpec("sangola", "09", 138, 0.43, True, (55.6, 55.6, 54.9, 55.1, 55.3)),
    TalukaSpec("north_solapur", "10", 92, 0.48, False, (57.6, 58.6, 59.0, 60.6, 60.9), n_vacancy=3),
    TalukaSpec("south_solapur", "11", 108, 0.56, False, (55.1, 56.3, 56.7, 57.3, 57.6), n_vacancy=3),
)
TALUKA_BY_KEY = {t.key: t for t in TALUKAS}

# School-level score model.
SCHOOL_EFFECT_SD = 7.0
SCHOOL_EFFECT_CLIP = 18.0
STUDENT_SD = 16.0  # sampling noise of a school mean = STUDENT_SD / sqrt(students appeared)
ORDINARY_EFFECT = 8.0  # planted vacancy schools are drawn from |effect| <= this

# T2 election duty.
ELECTION_YEAR = "2024-25"
ELECTION_MONTHS = {"2024-10": (38.0, 45.0), "2024-11": (45.0, 55.0)}  # heavy-duty talukas
ELECTION_LIGHT = {"2024-10": (4.0, 10.0), "2024-11": (6.0, 12.0)}  # other talukas
ELECTION_THRESHOLD = 30.0
ELECTION_MIN_MONTHS = 2
# Smaller duty spells in other years (all talukas, always below the threshold).
ELECTION_MINOR = {
    "2021-12": (3.0, 12.0),  # gram panchayat polls
    "2024-09": (2.0, 15.0),  # assembly poll training
    "2024-03": (8.0, 18.0),  # Lok Sabha preparation
    "2025-12": (10.0, 25.0),  # local body polls
}

# T5 flat attendance.
N_FLAT_FOCUS = 23
FLAT_FOCUS_MONTHS = ("2024-08", "2024-09", "2024-10", "2024-11")
N_FLAT_NOISE = 30
FLAT_RUN = 4
FLAT_NOISE_STARTS = ("2024-06", "2024-07", "2024-08", "2024-09")

# T6 insufficient data (Mangalvedha).
N_SPARSE_ATTENDANCE = 30  # miss 3-5 attendance months in Jun-Dec 2024
N_SPARSE_SCORES = 20  # miss 2 score years
N_SPARSE_OVERLAP = 4
SPARSE_WINDOW = ("2024-06", "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12")
BACKGROUND_ATTENDANCE_MISSING = 0.02  # share of schools per taluka missing exactly one month
SPARSE_LIGHT_MISSING = 0.20  # share of unflagged Mangalvedha schools missing 1-2 months
BACKGROUND_SCORE_MISSING = 0.025  # share of schools missing one score year (not focus/twin/decoy/sparse)

# T7 infrastructure.
INFRA_LOW_QUALITY = 0.30  # index ~ q + (1-q)/8 (partial classroom credit) -> about 0.40
INFRA_QUALITY_RANGE = (0.55, 0.68)  # -> index about 0.60-0.72
INFRA_MAX_ABS_R = 0.05  # enforced within the focus taluka

# T8 honest low attendance.
N_HONEST_LOW = 15
HONEST_BASE = (79.0, 83.0)
NORMAL_BASE = (84.0, 91.0)

# Teacher posts.
OTHER_VACANCY_RATE = 0.08
LANGUAGE_VACANCY_RATE = 0.03

# Name sets: key -> (display name, spelling variants, Devanagari).
NAME_SETS = {
    "solapur": {
        "akkalkot": ("Akkalkot", ("Akalkot", "Akkalkote"), "अक्कलकोट"),
        "barshi": ("Barshi", ("Barsi", "Baarshi"), "बार्शी"),
        "karmala": ("Karmala", ("Karmalla", "Karmale"), "करमाळा"),
        "madha": ("Madha", ("Maadha", "Madhe"), "माढा"),
        "malshiras": ("Malshiras", ("Malsiras", "Malshirus"), "माळशिरस"),
        "mangalvedha": ("Mangalvedha", ("Mangalwedha", "Mangalvedhe"), "मंगळवेढा"),
        "mohol": ("Mohol", ("Mohal", "Mohool"), "मोहोळ"),
        "pandharpur": ("Pandharpur", ("Pandharpoor", "Pandharpura"), "पंढरपूर"),
        "sangola": ("Sangola", ("Sangole", "Sangolla"), "सांगोला"),
        "north_solapur": ("North Solapur", ("N. Solapur", "Solapur North"), "उत्तर सोलापूर"),
        "south_solapur": ("South Solapur", ("S. Solapur", "Solapur South"), "दक्षिण सोलापूर"),
    },
    "fictional": {
        "akkalkot": ("Ambavati", ("Ambawati", "Ambavathi"), "अंबावती"),
        "barshi": ("Kusumgad", ("Kusumgadh", "Kusamgad"), "कुसुमगड"),
        "karmala": ("Tarapada", ("Tarapad", "Taraapada"), "तारापाडा"),
        "madha": ("Meghner", ("Meghaner", "Megner"), "मेघनेर"),
        "malshiras": ("Nilwadi", ("Neelwadi", "Nilawadi"), "नीलवाडी"),
        "mangalvedha": ("Ratnapura", ("Ratnapur", "Rathnapura"), "रत्नपुरा"),
        "mohol": ("Vasantgad", ("Wasantgad", "Vasantgadh"), "वसंतगड"),
        "pandharpur": ("Shivtara", ("Shivatara", "Sivtara"), "शिवतारा"),
        "sangola": ("Kamalpeth", ("Kamalpet", "Kamalpeeth"), "कमलपेठ"),
        "north_solapur": ("Uttar Sahyapur", ("N. Sahyapur", "Sahyapur North"), "उत्तर सह्यापूर"),
        "south_solapur": ("Dakshin Sahyapur", ("S. Sahyapur", "Sahyapur South"), "दक्षिण सह्यापूर"),
    },
}


def year_index(year: str) -> int:
    return YEARS.index(year)


def month_label(year: str, month: int) -> str:
    """Calendar label 'YYYY-MM' for a school month of an academic year like '2024-25'."""
    start = int(year[:4])
    return f"{start if month >= 6 else start + 1}-{month:02d}"


def months_of(year: str) -> list[str]:
    return [month_label(year, m) for m in SCHOOL_MONTHS]


def academic_year_of(label: str) -> str:
    y, m = int(label[:4]), int(label[5:])
    start = y if m >= 6 else y - 1
    return f"{start}-{(start + 1) % 100:02d}"
