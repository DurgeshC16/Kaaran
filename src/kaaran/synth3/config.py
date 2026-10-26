"""v3 generator configuration: block -> cluster (kendra) -> school, monthly operations, competency assessment.

Every planted scenario below has an id used by the answer key (truth3.json) and by docs/06_DECISION_RUBRICS.md.
Block names, poverty and school counts are shared with the v2 generator (synth/config.py) so both worlds agree.
"""

from __future__ import annotations

from ..synth import config as V2

STATE_PREFIX = V2.STATE_PREFIX  # "00": never a real UDISE state code
DISTRICT_CODE = V2.DISTRICT_CODE
DISTRICT_NAME = V2.DISTRICT_NAME

YEARS = ("2023-24", "2024-25", "2025-26")
SCHOOL_MONTHS = V2.SCHOOL_MONTHS  # Jun-Mar
ROUNDS = (("BL", "Baseline", "पायाभूत", 7), ("ML", "Midline", "मध्यावधी", 12), ("EL", "Endline", "अंतिम", 3))
GRADE = 3

# Competencies (grade 3), aligned in spirit with NIPUN Bharat / PRS foundational-stage competencies.
COMPETENCIES = {
    "M1": ("maths", "Number sense (numbers up to 999)", "संख्याज्ञान (९९९ पर्यंत)", 4.0),
    "M2": ("maths", "Place value", "स्थानिक किंमत", -6.0),
    "M3": ("maths", "Addition", "बेरीज", 2.0),
    "M4": ("maths", "Subtraction", "वजाबाकी", -4.0),
    "M5": ("maths", "Shapes and patterns", "आकार व आकृतिबंध", 3.0),
    "L1": ("language", "Letter-sound knowledge", "अक्षर-ध्वनी ओळख", 6.0),
    "L2": ("language", "Word reading", "शब्द वाचन", 2.0),
    "L3": ("language", "Reading fluency", "प्रवाही वाचन", -3.0),
    "L4": ("language", "Reading comprehension", "वाचन आकलन", -5.0),
}
ROUND_OFFSET = {"BL": -7.0, "ML": -2.5, "EL": 0.0}  # learning within the year (baseline after the summer break)

FOCUS = V2.FOCUS  # "pandharpur"
TWIN = V2.TWIN  # "malshiras": improves, similar profile
DECOY = V2.DECOY  # "sangola": similar profile, does not improve
REPLICATION_BLOCK = "madha"  # a second support-gap cluster elsewhere (replication for STRONG)

# Block level: mean grade-3 maths % at EL of each year (2023-24, 2024-25, 2025-26) before planted effects.
BLOCK_LEVEL = {
    "akkalkot": (60.0, 60.5, 60.2), "barshi": (66.0, 67.0, 68.0), "karmala": (59.0, 59.5, 59.0),
    "madha": (63.5, 64.5, 65.0), "malshiras": (61.0, 64.0, 67.5), "mangalvedha": (58.0, 58.0, 58.5),
    "mohol": (62.0, 62.5, 63.5), "pandharpur": (63.0, 63.5, 63.8), "sangola": (62.5, 62.6, 62.4),
    "north_solapur": (65.0, 66.0, 66.5), "south_solapur": (61.5, 62.5, 63.0),
}
LANGUAGE_OVER_MATHS = 5.0  # language is a little higher than maths (as in PRS 2024)
CLUSTER_SD = 2.5
SCHOOL_SD = 6.0
SCHOOL_CLIP = 15.0
SCHOOL_TREND_SD = 0.8  # per year

# Cluster roles inside the focus block (cluster index 1..n; see truth3.json for the generated ids).
SUPPORT_GAP = 3  # Kendra Pramukh post vacant from Jun 2025: visits collapse, last training 2023-24
STAFFING_GAP = 7  # 5 schools lose a teacher in the Jun 2025 transfers (single-teacher multigrade), + 1 positive deviant
HONEST_LOW = 5  # 4 schools with naturally low, plausible attendance (must be cleared, not flagged)
IMPROVING = 8
DATA_PROBLEM = 9  # 7 schools report 100% attendance Aug-Nov 2025 while learning is low
SURPLUS = 10  # 2 schools with falling enrolment and 4 teachers (PTR < 18): redeployment is possible
MIGRATION = 11  # 5 schools near sugar factories: attendance falls Nov-Mar every year; endline lower
INSUFFICIENT = 12  # 4 schools miss attendance months and the 2025-26 endline

# Support gap (cluster SUPPORT_GAP of the focus block, and one cluster of REPLICATION_BLOCK).
SUPPORT_GAP_START = "2025-06"
KP_VISIT_RATE = 1.3  # Kendra Pramukh visits per school per month, normal
KP_VISIT_RATE_GAP = 0.12
BRC_VISIT_RATE = 0.20
BEO_VISIT_RATE = 0.08
SUPPORT_GAP_EFFECT = {"ML": -4.0, "EL": -8.5}  # 2025-26, all competencies
SUPPORT_GAP_COMPETENCY = {"M2": -15.0, "M4": -14.0}  # extra on top, the competency signature
SUPPORT_GAP_LANGUAGE_FACTOR = 0.4

# Staffing gap.
STAFFING_GAP_SCHOOLS = 6
STAFFING_GAP_START = "2025-06"  # teacher transfers happen in May-June
STAFFING_GAP_EFFECT = {"2025-26": -18.0}  # ramps over the year: BL 40%, ML 80%, EL 100%
POSITIVE_DEVIANT_GAIN = {"2025-26": 12.0}
STAFFING_ELSEWHERE_PER_BLOCK = 2  # vacancy-exposed schools in other blocks (replication)

# Surplus schools.
SURPLUS_SCHOOLS = 2
SURPLUS_TEACHERS = 4
SURPLUS_ENROLMENT = (55, 66)  # whole school, classes 1-5

# Data problem (flat attendance + low learning).
FLAT_SCHOOLS = 7
FLAT_MONTHS = ("2025-08", "2025-09", "2025-10", "2025-11")
FLAT_LEARNING_SHIFT = -10.0
FLAT_ELSEWHERE = 6  # scattered single flat schools district-wide (noise the rules must tolerate at cluster level)

# Seasonal migration.
MIGRATION_SCHOOLS = 5
MIGRATION_DROP = {11: -10.0, 12: -18.0, 1: -20.0, 2: -19.0, 3: -15.0}  # children away at sugarcane cutting
MIGRATION_EL_EFFECT = -7.0  # endline of every year (children away during Nov-Mar)
MIGRATION_CLUSTER_SHIFT = -2.0

# Insufficient data.
INSUFFICIENT_SCHOOLS = 4
INSUFFICIENT_MISSING_MONTHS = ("2025-08", "2025-09", "2025-10", "2025-11")

# Honest low attendance.
HONEST_LOW_SCHOOLS = 4
HONEST_BASE = (77.0, 81.0)
NORMAL_BASE = (84.0, 91.0)
ATTENDANCE_CAP = 97.5
SEASONAL_ATTENDANCE = V2.SEASONAL_ATTENDANCE

# Improving cluster.
IMPROVING_GAIN = {"2024-25": 2.0, "2025-26": 4.5}

# Non-teaching duty (local body polls, all blocks).
DUTY_MONTHS = {"2025-11": (8.0, 12.0), "2025-12": (6.0, 9.0), "2024-03": (3.0, 5.0)}  # avg duty days per teacher
DUTY_BACKGROUND = (0.0, 1.5)
DUTY_ML_EFFECT = -2.5  # 2025-26 midline, every school in the district; gone by the endline

# Teacher posts.
PUPILS_PER_POST = 30  # RTE primary norm
MIN_POSTS = 2
RANDOM_VACANCY_RATE = 0.04
CONTRACT_SHARE = 0.12

# Training (block-level FLN maths pedagogy trainings, August of each year).
TRAINING_MONTH = 8
TRAINING_DAYS = 3

CLASS_SIZE_POVERTY_SLOPE = 2.0  # class size factor = 1 + slope * (ref - block poverty)
CLASS_SIZE_POVERTY_REF = 0.45
ASSESSED_SHARE = (0.85, 0.97)  # share of grade-3 enrolment assessed in a round
