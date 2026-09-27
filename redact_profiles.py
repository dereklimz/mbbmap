"""
redact_profiles.py

Reads "cleaned_profiles.csv" and writes "profiles_redacted.csv" for publishing:
  - name        → removed
  - profile_id  → sequential pseudonym (person-0001, person-0002, ...)
  - drops any column that could link back to a LinkedIn profile
    (url, avatar, linkedin ids, bios) if present

Usage:  python redact_profiles.py [input_csv] [output_csv]
"""

import sys

import pandas as pd

CSV_IN = "cleaned_profiles.csv"
CSV_OUT = "profiles_redacted.csv"

IDENTIFYING_COLS = [
    "name", "first_name", "last_name", "url", "input_url", "avatar",
    "banner_image", "linkedin_id", "linkedin_num_id", "about", "bio_links",
]


def redact(input_csv: str, output_csv: str) -> int:
    df = pd.read_csv(input_csv, low_memory=False)
    # Same person can appear twice in the source; keep last, like data_loader's INSERT OR REPLACE
    df = df.drop_duplicates(subset="profile_id", keep="last")
    df = df[df["has_mbb"] == 1]  # publish MBB alumni only
    df = df.drop(columns=[c for c in IDENTIFYING_COLS if c in df.columns])
    df = df.sample(frac=1, random_state=0).reset_index(drop=True)  # break original ordering
    df["profile_id"] = [f"person-{i:04d}" for i in range(1, len(df) + 1)]
    df.to_csv(output_csv, index=False)
    return len(df)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else CSV_IN
    dst = sys.argv[2] if len(sys.argv) > 2 else CSV_OUT
    n = redact(src, dst)
    print(f"Wrote {n:,} redacted profiles to {dst}")
