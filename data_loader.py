"""
data_loader.py — Load MBB profiles CSV into SQLite.

Expected CSV columns (from clean_profiles.py in CareerLens):
  profile_id, name, location, current_title, current_company,
  mba_school, mba_year, undergrad_school, undergrad_year,
  has_mbb, mbb_firms,
  exp_1_company, exp_1_title, exp_1_all_titles, exp_1_start, exp_1_end, exp_1_is_mbb, exp_1_mbb_firm,
  exp_2_company, ...  (up to N)
"""

import re
import sqlite3
import sys
from typing import Any

import pandas as pd

DB_PATH = "mbbmap.db"


def load_csv(csv_path: str, db_path: str = DB_PATH) -> str:
    df = pd.read_csv(csv_path, low_memory=False)

    # Enforce the same filters applied in clean_profiles.py
    before = len(df)
    df = df[~((df["has_mbb"] == 1) & df["mbb_company"].isna())]   # intern-only MBB
    df = df[~((df["has_mbb"] == 1) & df["post_mbb_company"].isna())]  # no post-MBB path
    dropped = before - len(df)
    if dropped:
        print(f"  Filtered out {dropped:,} profiles (intern-only or no post-MBB path)")

    # Detect experience columns
    exp_cols = sorted(
        {int(m.group(1)) for c in df.columns if (m := re.match(r"exp_(\d+)_company", c))}
    )
    max_exp = max(exp_cols) if exp_cols else 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Build dynamic experience columns for the table
    exp_col_defs = []
    for i in range(1, max_exp + 1):
        exp_col_defs += [
            f"exp_{i}_company TEXT",
            f"exp_{i}_title TEXT",
            f"exp_{i}_all_titles TEXT",
            f"exp_{i}_start TEXT",
            f"exp_{i}_end TEXT",
            f"exp_{i}_is_mbb INTEGER",
            f"exp_{i}_mbb_firm TEXT",
        ]

    exp_col_block = (", " + ", ".join(exp_col_defs)) if exp_col_defs else ""
    cur.executescript(f"""
        DROP TABLE IF EXISTS profiles;
        CREATE TABLE profiles (
            profile_id        TEXT PRIMARY KEY,
            name              TEXT,
            location          TEXT,
            current_title     TEXT,
            current_company   TEXT,
            mba_school        TEXT,
            mba_year          TEXT,
            ms_school         TEXT,
            ms_year           TEXT,
            phd_school        TEXT,
            phd_year          TEXT,
            jd_school         TEXT,
            jd_year           TEXT,
            undergrad_school  TEXT,
            undergrad_year    TEXT,
            has_mbb           INTEGER,
            mbb_firms         TEXT,
            mbb_company       TEXT,
            mbb_firm          TEXT,
            mbb_title         TEXT,
            mbb_start         TEXT,
            mbb_end           TEXT,
            post_mbb_company  TEXT,
            post_mbb_title    TEXT{exp_col_block}
        );
        CREATE INDEX IF NOT EXISTS idx_current_company ON profiles(current_company);
        CREATE INDEX IF NOT EXISTS idx_mba_school ON profiles(mba_school);
        CREATE INDEX IF NOT EXISTS idx_has_mbb ON profiles(has_mbb);
    """)

    def _s(val):
        if val is None or (isinstance(val, float) and val != val):
            return None
        s = str(val).strip()
        return None if s.lower() in ("", "nan") else s

    def _b(val):
        if val is None or (isinstance(val, float) and val != val):
            return 0
        return 1 if str(val).strip().lower() in ("true", "1", "yes") else 0

    base_cols = [
        "profile_id", "name", "location", "current_title", "current_company",
        "mba_school", "mba_year", "ms_school", "ms_year",
        "phd_school", "phd_year", "jd_school", "jd_year",
        "undergrad_school", "undergrad_year",
        "has_mbb", "mbb_firms",
        "mbb_company", "mbb_firm", "mbb_title", "mbb_start", "mbb_end",
        "post_mbb_company", "post_mbb_title",
    ]
    all_col_names = base_cols + [c for i in range(1, max_exp + 1) for c in [
        f"exp_{i}_company", f"exp_{i}_title", f"exp_{i}_all_titles",
        f"exp_{i}_start", f"exp_{i}_end", f"exp_{i}_is_mbb", f"exp_{i}_mbb_firm",
    ]]

    placeholders = ", ".join(["?"] * len(all_col_names))
    insert_sql = f"INSERT OR REPLACE INTO profiles ({', '.join(all_col_names)}) VALUES ({placeholders})"

    rows = []
    for _, row in df.iterrows():
        values = [
            _s(row.get("profile_id")), _s(row.get("name")), _s(row.get("location")),
            _s(row.get("current_title")), _s(row.get("current_company")),
            _s(row.get("mba_school")), _s(row.get("mba_year")),
            _s(row.get("ms_school")), _s(row.get("ms_year")),
            _s(row.get("phd_school")), _s(row.get("phd_year")),
            _s(row.get("jd_school")), _s(row.get("jd_year")),
            _s(row.get("undergrad_school")), _s(row.get("undergrad_year")),
            _b(row.get("has_mbb")), _s(row.get("mbb_firms")),
            _s(row.get("mbb_company")), _s(row.get("mbb_firm")),
            _s(row.get("mbb_title")), _s(row.get("mbb_start")), _s(row.get("mbb_end")),
            _s(row.get("post_mbb_company")), _s(row.get("post_mbb_title")),
        ]
        for i in range(1, max_exp + 1):
            values += [
                _s(row.get(f"exp_{i}_company")),
                _s(row.get(f"exp_{i}_title")),
                _s(row.get(f"exp_{i}_all_titles")),
                _s(row.get(f"exp_{i}_start")),
                _s(row.get(f"exp_{i}_end")),
                _b(row.get(f"exp_{i}_is_mbb")),
                _s(row.get(f"exp_{i}_mbb_firm")),
            ]
        rows.append(values)

    cur.executemany(insert_sql, rows)
    conn.commit()
    conn.close()

    return db_path


def get_summary_stats(db_path: str = DB_PATH) -> dict[str, Any]:
    """Return high-level counts for dashboard overview cards."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    stats: dict[str, Any] = {}

    cur.execute("SELECT COUNT(*) FROM profiles")
    stats["total_profiles"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM profiles WHERE has_mbb = 1")
    stats["mbb_profiles"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mba_school) FROM profiles WHERE mba_school IS NOT NULL")
    stats["mba_schools"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT current_company) FROM profiles WHERE current_company IS NOT NULL")
    stats["current_companies"] = cur.fetchone()[0]

    # Top MBB firm breakdown from the mbb_firms text field
    cur.execute("""
        SELECT mbb_firms, COUNT(*) as cnt
        FROM profiles
        WHERE has_mbb = 1 AND mbb_firms IS NOT NULL
        GROUP BY mbb_firms
        ORDER BY cnt DESC
    """)
    stats["mbb_firm_counts"] = {row[0]: row[1] for row in cur.fetchall()}

    conn.close()
    return stats


def get_filter_options(db_path: str = DB_PATH) -> dict[str, list[str]]:
    """Return distinct values for Streamlit dropdown/multiselect filters."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    def _distinct(column: str, table: str = "profiles") -> list[str]:
        cur.execute(
            f"SELECT DISTINCT {column} FROM {table} "
            f"WHERE {column} IS NOT NULL ORDER BY {column}"
        )
        return [row[0] for row in cur.fetchall()]

    options = {
        "mba_school": _distinct("mba_school"),
        "undergrad_school": _distinct("undergrad_school"),
        "current_company": _distinct("current_company"),
        "location": _distinct("location"),
    }

    # Collect all unique MBB firm names from mbb_firms (may be comma-separated)
    cur.execute("SELECT DISTINCT mbb_firms FROM profiles WHERE mbb_firms IS NOT NULL")
    raw_firms: set[str] = set()
    for (val,) in cur.fetchall():
        for firm in re.split(r"[,;|]", val):
            firm = firm.strip()
            if firm:
                raw_firms.add(firm)
    options["mbb_firm"] = sorted(raw_firms)

    conn.close()
    return options


def query_profiles(
    db_path: str = DB_PATH,
    *,
    mba_schools: list[str] | None = None,
    mbb_firms: list[str] | None = None,
    current_companies: list[str] | None = None,
    locations: list[str] | None = None,
    has_mbb: bool | None = None,
    mba_year_range: tuple[int, int] | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """Return filtered profiles as a DataFrame.

    All filters are optional; omitting one means no restriction on that field.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if has_mbb is not None:
        conditions.append("has_mbb = ?")
        params.append(1 if has_mbb else 0)

    if mba_schools:
        placeholders = ", ".join(["?"] * len(mba_schools))
        conditions.append(f"mba_school IN ({placeholders})")
        params.extend(mba_schools)

    if current_companies:
        placeholders = ", ".join(["?"] * len(current_companies))
        conditions.append(f"current_company IN ({placeholders})")
        params.extend(current_companies)

    if locations:
        placeholders = ", ".join(["?"] * len(locations))
        conditions.append(f"location IN ({placeholders})")
        params.extend(locations)

    if mbb_firms:
        # mbb_firms column may contain multiple firms; match any
        firm_conds = " OR ".join(["mbb_firms LIKE ?"] * len(mbb_firms))
        conditions.append(f"({firm_conds})")
        params.extend([f"%{f}%" for f in mbb_firms])

    if mba_year_range:
        lo, hi = mba_year_range
        conditions.append("CAST(mba_year AS INTEGER) BETWEEN ? AND ?")
        params.extend([lo, hi])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM profiles {where} LIMIT ?"
    params.append(limit)

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_schema(db_path: str = DB_PATH) -> str:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='profiles'")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def get_max_exp(db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(profiles)")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    nums = [int(m.group(1)) for c in cols if (m := re.match(r"exp_(\d+)_company", c))]
    return max(nums) if nums else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data_loader.py <csv_path> [db_path]")
        sys.exit(1)

    csv_path = sys.argv[1]
    db = sys.argv[2] if len(sys.argv) > 2 else DB_PATH

    print(f"Loading {csv_path} → {db} ...")
    load_csv(csv_path, db)

    stats = get_summary_stats(db)
    print(f"  Profiles loaded : {stats['total_profiles']:,}")
    print(f"  Has MBB exp     : {stats['mbb_profiles']:,}")
    print(f"  MBA schools     : {stats['mba_schools']:,}")
    print(f"  Current companies: {stats['current_companies']:,}")
    if stats["mbb_firm_counts"]:
        print("  MBB firm breakdown:")
        for firm, cnt in stats["mbb_firm_counts"].items():
            print(f"    {firm}: {cnt:,}")
    print("Done.")
