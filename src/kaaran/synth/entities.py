"""Static entities: talukas and schools (codes, names, clusters, enrolment, infrastructure)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .rng import stream

VILLAGE_HEADS = (
    "Khand", "Shiv", "Kesar", "Mal", "Pim", "Sav", "Dhan", "Kur", "Bhos", "Ran",
    "Jaw", "Tak", "Ghat", "Hing", "Kas", "Lon", "Var", "Ambe", "Nimb", "Bor",
    "Chin", "Ped", "Jam", "Sonal", "Up", "Gad", "Kond", "Mhas", "Pat", "Wak",
    "Ter", "Kav", "Bhal", "Ved", "Sir", "Ane", "Pal", "Dhok", "Mand", "Wan",
)
VILLAGE_TAILS = (
    "wadi", "gaon", "pur", "ner", "kheda", "oli", "ale", "wade",
    "phal", "ewadi", "angaon", "ur", "wad", "dari", "tanda", "nagar",
)
SCHOOL_PREFIXES = (
    ("ZP Primary School", 0.75),
    ("ZP Marathi Primary School", 0.17),
    ("ZP Urdu Primary School", 0.08),
)
KENDRA_PREFIX = "ZP Kendra Primary School"
VOWELS = set("aeiou")


def _village(head: str, tail: str) -> str:
    if head[-1].lower() in VOWELS and tail[0] in VOWELS:
        head = head[:-1]
    return head + tail


def build_talukas(names: str) -> pd.DataFrame:
    name_set = C.NAME_SETS[names]
    rows = []
    for t in C.TALUKAS:
        name, _variants, name_mr = name_set[t.key]
        rows.append(
            {
                "taluka_key": t.key,
                "block_code": t.block,
                "taluka": name,
                "taluka_mr": name_mr,
                "poverty_index": t.poverty,
                "n_schools": t.n_schools,
            }
        )
    return pd.DataFrame(rows)


def _cluster_sizes(n: int) -> list[int]:
    k = max(1, round(n / 12.5))
    return [n // k + (1 if i < n % k else 0) for i in range(k)]


def draw_infra(enrol_total: np.ndarray, quality: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """Infrastructure columns; each component is adequate with probability `quality`."""
    n = len(enrol_total)
    ok = rng.random((n, 4)) < quality[:, None]
    toilets = np.where(ok[:, 0], 2 + rng.binomial(2, 0.5, n), rng.binomial(1, 0.5, n))
    need = np.maximum(2, np.ceil(enrol_total / 30)).astype(int)
    short = np.array([rng.integers(1, k) for k in need])  # 1..need-1 rooms short
    classrooms = np.where(ok[:, 3], need + rng.integers(0, 3, n), need - short)
    library = ok[:, 1].astype(int)
    water = ok[:, 2].astype(int)
    index = ((toilets >= 2).astype(float) + library + water + np.minimum(1.0, classrooms / need)) / 4
    return pd.DataFrame(
        {
            "toilets": toilets.astype(int),
            "library": library,
            "drinking_water": water,
            "classrooms": classrooms.astype(int),
            "infra_index": np.round(index, 3),
        }
    )


def _draw_enrolment(n: int, rng: np.random.Generator) -> np.ndarray:
    total = np.round(20 + 130 * rng.beta(2.2, 2.2, n)).astype(int)
    by_std = np.array([rng.multinomial(t, rng.dirichlet([12.0] * 5)) for t in total])
    return by_std  # shape (n, 5), Std 1-5


def build_schools(seed: int, names: str) -> pd.DataFrame:
    rng = stream(seed, "schools")
    name_set = C.NAME_SETS[names]
    all_villages = [_village(h, t) for h in VILLAGE_HEADS for t in VILLAGE_TAILS]
    frames = []
    for t in C.TALUKAS:
        n = t.n_schools
        n_villages = round(n * 0.82)
        villages = [all_villages[i] for i in rng.choice(len(all_villages), n_villages, replace=False)]
        codes = np.sort(rng.choice(np.arange(1, 400), n_villages, replace=False))
        per_village = np.ones(n_villages, dtype=int)
        np.add.at(per_village, rng.choice(n_villages, n - n_villages), 1)
        rows = []
        for v_name, v_code, k in zip(villages, codes, per_village):
            for serial in range(1, k + 1):
                rows.append((v_name, int(v_code), serial))
        df = pd.DataFrame(rows, columns=["village", "village_code", "serial"])
        df = df.sort_values(["village_code", "serial"], ignore_index=True)
        df["udise_code"] = [
            f"{C.STATE_PREFIX}{C.DISTRICT_CODE}{t.block}{vc:03d}{s:02d}"
            for vc, s in zip(df["village_code"], df["serial"])
        ]
        prefixes = [p for p, _ in SCHOOL_PREFIXES]
        weights = [w for _, w in SCHOOL_PREFIXES]
        df["prefix"] = rng.choice(prefixes, n, p=weights)
        cluster_ids, cluster_names = [], []
        start = 0
        for c, size in enumerate(_cluster_sizes(n), start=1):
            df.loc[start, "prefix"] = KENDRA_PREFIX
            cluster_ids += [f"{t.block}{c:02d}"] * size
            cluster_names += [f"Kendra {df.loc[start, 'village']}"] * size
            start += size
        df["cluster_code"] = cluster_ids
        df["cluster"] = cluster_names
        df["school_name"] = [
            f"{p} {v}" + (f" No. {s}" if s > 1 else "")
            for p, v, s in zip(df["prefix"], df["village"], df["serial"])
        ]
        df["taluka_key"] = t.key
        df["taluka"] = name_set[t.key][0]
        frames.append(df)
    schools = pd.concat(frames, ignore_index=True)

    n_all = len(schools)
    short = rng.choice(np.arange(10000, 100000), n_all, replace=False)
    schools["short_code"] = [f"SC{s:05d}" for s in short]

    enrol = np.zeros((n_all, 5), dtype=int)
    for t in C.TALUKAS:
        idx = np.flatnonzero(schools["taluka_key"].to_numpy() == t.key)
        enrol[idx] = _draw_enrolment(len(idx), rng)
    # T4: twin and decoy match the focus taluka's mean enrolment within 3%.
    focus_idx = np.flatnonzero(schools["taluka_key"].to_numpy() == C.FOCUS)
    focus_mean = enrol[focus_idx].sum(axis=1).mean()
    for key in (C.TWIN, C.DECOY):
        idx = np.flatnonzero(schools["taluka_key"].to_numpy() == key)
        for _ in range(500):
            if abs(enrol[idx].sum(axis=1).mean() / focus_mean - 1) <= 0.03:
                break
            enrol[idx] = _draw_enrolment(len(idx), rng)
        else:
            raise RuntimeError(f"could not match enrolment for {key}")
    for i in range(5):
        schools[f"enrol_std{i + 1}"] = enrol[:, i]
    schools["enrol_total"] = enrol.sum(axis=1)

    quality_by_taluka = {
        t.key: (C.INFRA_LOW_QUALITY if t.key == C.INFRA_LOW else rng.uniform(*C.INFRA_QUALITY_RANGE))
        for t in C.TALUKAS
    }
    quality = schools["taluka_key"].map(quality_by_taluka).to_numpy(dtype=float)
    infra = draw_infra(schools["enrol_total"].to_numpy(), quality, rng)
    schools = pd.concat([schools, infra], axis=1)
    schools["infra_quality"] = quality  # latent, dropped before writing

    columns = [
        "udise_code", "short_code", "school_name", "village", "taluka_key", "taluka",
        "cluster_code", "cluster", "enrol_std1", "enrol_std2", "enrol_std3", "enrol_std4",
        "enrol_std5", "enrol_total", "toilets", "library", "drinking_water", "classrooms",
        "infra_index", "infra_quality",
    ]
    return schools[columns]
