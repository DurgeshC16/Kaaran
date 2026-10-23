"""Hold-out raw layouts for testing the mapping proposer.

`default` writes the files exactly as before. `variant_b` keeps every value but changes how the xlsx and csv
files look:
- headers reworded in English, Marathi and transliterated Marathi;
- columns shuffled; junk columns added; sheets renamed; the Enrolment group header row dropped.
The PDF is unchanged (its header stays rule-parsed). The transform is recorded as a layout key in
ground_truth.json so the eval can score a proposed mapping against it.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .rng import stream

LAYOUTS = ("default", "variant_b")

# (file, original header) -> variant_b header
HEADERS_B = {
    ("udise_2023.xlsx", "UDISE Code"): "Shala UDISE Kramank",
    ("udise_2023.xlsx", "school NAME"): "शाळेचे संपूर्ण नाव",
    ("udise_2023.xlsx", "TALUKA"): "Block / Taluka Name",
    ("udise_2023.xlsx", "Cluster"): "Kendra",
    ("udise_2023.xlsx", "cluster code"): "Kendra Sanket",
    ("udise_2023.xlsx", "Village Name"): "गावाचे नाव",
    ("udise_2023.xlsx", "Management"): "Vyavasthapan",
    ("udise_2023.xlsx", "School Name"): "Name of the School",
    ("udise_2023.xlsx", "Taluka"): "तालुका नाव",
    ("udise_2023.xlsx", "Std 1"): "इयत्ता पहिली",
    ("udise_2023.xlsx", "Std 2"): "इयत्ता दुसरी",
    ("udise_2023.xlsx", "Std 3"): "इयत्ता तिसरी",
    ("udise_2023.xlsx", "Std 4"): "इयत्ता चौथी",
    ("udise_2023.xlsx", "Std 5"): "इयत्ता पाचवी",
    ("udise_2023.xlsx", "Total"): "Ekun Patsankhya",
    ("udise_2023.xlsx", "यूडायस कोड"): "UDISE No.",
    ("udise_2023.xlsx", "शाळेचे नाव"): "Shalecha Naav",
    ("udise_2023.xlsx", "तालुका"): "Taluka (तालुका)",
    ("udise_2023.xlsx", "शौचालये"): "Functional Toilets",
    ("udise_2023.xlsx", "ग्रंथालय"): "Library Available?",
    ("udise_2023.xlsx", "पिण्याचे पाणी"): "Pinyache Pani",
    ("udise_2023.xlsx", "वर्गखोल्या"): "No. of Classrooms",
    ("crosswalk.xlsx", "Short Code"): "Hajeri Sanket",
    ("crosswalk.xlsx", "UDISE Code"): "UDISE क्रमांक",
    ("crosswalk.xlsx", "Taluka"): "Block",
    ("teacher_posts.xlsx", "UDISE Code"): "School UDISE",
    ("teacher_posts.xlsx", "School Name"): "शाळा",
    ("teacher_posts.xlsx", "Taluka"): "Taluka Name",
    ("teacher_posts.xlsx", "Subject"): "Vishay",
    ("teacher_posts.xlsx", "Sanctioned"): "मंजूर पदे",
    ("teacher_posts.xlsx", "Working"): "Karyarat",
    ("teacher_posts.xlsx", "Vacant"): "रिक्त",
    ("teacher_posts.xlsx", "As On"): "Dinank Paryant",
    ("pat_scores.csv", "SCHOOL_CD"): "UDISE_NO",
    ("pat_scores.csv", "Year"): "Shaikshanik Varsh",
    ("pat_scores.csv", "Std"): "इयत्ता",
    ("pat_scores.csv", "Subject"): "Vishay",
    ("pat_scores.csv", "Avg_Marks"): "Sarasari Gun",
    ("pat_scores.csv", "Students_Appeared"): "Basalele Vidyarthi",
    ("election_duty.csv", "Sr.No.", ): "Anu. Kr.",
    ("election_duty.csv", "Taluka"): "Block",
    ("election_duty.csv", "Duty"): "Kartavya Prakar",
    ("election_duty.csv", "From"): "Paasun",
    ("election_duty.csv", "To"): "Paryant",
    ("election_duty.csv", "Deployed Teachers (%)"): "Niyukt Shikshak Takka",
    ("taluka_profile.csv", "Taluka"): "तालुका",
    ("taluka_profile.csv", "Poverty Headcount Ratio (%)"): "Daridrya Pramaan (%)",
}
SHEETS_B = {
    ("udise_2023.xlsx", "School Profile"): "शाळा माहिती",
    ("udise_2023.xlsx", "Enrolment"): "Patsankhya",
    ("udise_2023.xlsx", "Infrastructure"): "Bhautik Suvidha",
    ("crosswalk.xlsx", "Crosswalk"): "Code Map",
}
JUNK_B = {  # junk columns per (file, sheet); values carry no data and no personal names
    ("udise_2023.xlsx", "School Profile"): ["Remarks", "Unnamed: 9"],
    ("udise_2023.xlsx", "Enrolment"): ["Checked By"],
    ("udise_2023.xlsx", "Infrastructure"): ["Entry Date"],
    ("crosswalk.xlsx", "Crosswalk"): ["Remarks"],
    ("teacher_posts.xlsx", None): ["Remarks"],
    ("pat_scores.csv", None): ["Unnamed: 7"],
    ("election_duty.csv", None): ["Remarks"],
    ("taluka_profile.csv", None): ["Source"],
}


class VariantB:
    def __init__(self, seed: int):
        self.seed = seed
        self.tables: list[dict] = []
        self.sheet_map: dict[tuple[str, str], str] = {}

    def _junk(self, name: str, n: int, rng) -> list:
        if name.startswith("Unnamed"):
            return [None] * n
        if name == "Remarks":
            return list(rng.choice(np.array(["", "ok", "verified", "see note"], dtype=object), n))
        if name == "Checked By":
            return list(rng.choice(np.array(["Clerk A", "Clerk B", ""], dtype=object), n))
        if name == "Entry Date":
            return [f"{int(d):02d}/0{int(m)}/2023" for d, m in zip(rng.integers(1, 29, n), rng.integers(1, 10, n))]
        return ["Block office"] * n  # Source

    def _frame(self, file: str, sheet: str | None, frame: pd.DataFrame, junk_key, header_shift: int = 0) -> pd.DataFrame:
        rng = stream(self.seed, f"layout:variant_b:{file}:{sheet}")
        renames = {c: HEADERS_B.get((file, c), c) for c in frame.columns}
        out = frame.rename(columns=renames)
        junk = JUNK_B.get(junk_key, [])
        for j in junk:
            out[j] = self._junk(j, len(out), rng)
        order = [out.columns[i] for i in rng.permutation(len(out.columns))]
        out = out[order]
        sheet_to = SHEETS_B.get((file, sheet), sheet)
        if file == "teacher_posts.xlsx" and sheet:
            sheet_to = f"Posts {sheet}" if int(sheet[:4]) % 2 else f"शिक्षक पदे {sheet}"
        if sheet is not None:
            self.sheet_map[(file, sheet)] = sheet_to
        self.tables.append({"file": file, "sheet_from": sheet, "sheet_to": sheet_to, "headers": renames,
                            "junk": junk, "order": [str(c) for c in order], "header_row_shift": header_shift})
        return out

    def sheet(self, file: str, s):
        junk_key = (file, None) if file == "teacher_posts.xlsx" else (file, s.name)
        frame = self._frame(file, s.name, s.frame, junk_key, header_shift=-1 if s.group_header else 0)
        text_columns = tuple(HEADERS_B.get((file, c), c) for c in s.text_columns)
        return replace(s, name=self.sheet_map[(file, s.name)], frame=frame, group_header=[], text_columns=text_columns)

    def csv(self, file: str, frame: pd.DataFrame) -> pd.DataFrame:
        return self._frame(file, None, frame, (file, None))

    def key(self) -> dict:
        return {"name": "variant_b", "tables": self.tables}
