"""
clean_profiles.py — Transform raw LinkedIn CSV into the format expected by data_loader.py.

Input:  raw LinkedIn scrape CSV (LinkedIn people profiles.csv)
Output: cleaned_profiles.csv

MBB detection covers McKinsey, BCG, and Bain.
"""

import json
import os
import re
import sys

import pandas as pd

MBB_PATTERNS = {
    "McKinsey": re.compile(r"mckinsey", re.I),
    "BCG": re.compile(r"boston consulting|bcg\b", re.I),
    "Bain": re.compile(r"\bbain\b(?! capital)", re.I),
}

INTERN_RE = re.compile(
    r"\bintern(ship)?\b|\bfellow(ship)?\b|\bco-?op\b|\bsummer\b|\bstudent\b|"
    r"forward program|bcg rise|\bpre-?mba\b|leadership program|"
    r"diversity program|insight program|immersion program|"
    r"\bcandidate\b|postdoctoral|\badministrative assistant\b", re.I
)

MBA_KEYWORDS = re.compile(
    r"\b(mba|masters? of business administration|m\.b\.a)\b", re.I
)
MS_KEYWORDS = re.compile(
    r"\b(master of science|m\.s\.?|msc|master of engineering|m\.eng|master of arts|m\.a\.?|"
    r"master of public policy|master of public administration|mpa|master of finance|"
    r"master of education|master of laws|ll\.m|master of philosophy|mphil|"
    r"masters? of|master in)\b", re.I
)
PHD_KEYWORDS = re.compile(
    r"\b(ph\.?d\.?|doctor of philosophy|d\.phil|doctorate)\b", re.I
)
JD_KEYWORDS = re.compile(
    r"\b(j\.?d\.?|juris doctor|juris doctorate|doctor of law)\b", re.I
)
MBA_SCHOOLS = re.compile(
    # ── Catch-all: any school with standard business school naming ──
    r"(school of business"
    r"|business school"
    r"|school of management"
    r"|college of business"
    r"|graduate school of business"
    # ── Named US schools ──
    r"|\bhbs\b|harvard business school"
    r"|wharton school"
    r"|mit sloan|sloan school of management"
    r"|stanford.*school of business|stanford gsb"
    r"|kellogg school of management"
    r"|booth school of business|chicago booth"
    r"|columbia business school"
    r"|tuck school of business"
    r"|fuqua school of business"
    r"|stern school of business"
    r"|darden school of business|darden graduate school"
    r"|haas school of business"
    r"|yale school of management"
    r"|goizueta business school"
    r"|mccombs school of business"
    r"|ross school of business|stephen m\. ross"
    r"|foster school of business"
    r"|johnson.*school.*management"
    r"|tepper school of business"
    r"|mendoza college of business"
    r"|mcdonough school of business"
    r"|marshall school of business"
    r"|anderson school of management"
    r"|carroll school of management"
    r"|cox school of business"
    r"|kelley school of business"
    r"|olin business school|olin graduate school"
    r"|smith school of business"
    r"|carey business school"
    r"|kenan-flagler business school"
    r"|ivey business school"
    r"|owen graduate school"
    r"|jones graduate school"
    r"|questrom school"
    r"|gabelli school"
    r"|whitman school of management"
    r"|eller college"
    r"|lundquist college"
    r"|smeal college"
    r"|fisher college of business"
    r"|mays business school"
    r"|warrington college"
    r"|broad college of business|\beli broad\b"
    r"|isenberg school"
    r"|poole college"
    r"|darla moore school"
    r"|spears school"
    r"|price college of business"
    r"|walton college"
    r"|rawls college"
    r"|farmer school of business"
    r"|lerner college"
    # ── Named international schools ──
    r"|\binsead\b"
    r"|london business school|\blbs\b(?! )"
    r"|iese business school"
    r"|ie business school"
    r"|said business school|sa\u00efd business school"
    r"|judge business school"
    r"|indian school of business|\bisb\b"
    r"|schulich school of business"
    r"|rotman school of management"
    r"|sauder school of business"
    r"|carlson school of management"
    r"|desautels faculty"
    r"|\bimd\b"
    r"|sda bocconi"
    r"|\besade\b"
    r"|st\. gallen|university of st\. gallen"
    r"|rotterdam school of management"
    r"|copenhagen business school"
    r"|norwegian school of economics|\bnhh\b"
    r"|emlyon|em lyon"
    r"|grenoble.*management"
    r"|\bessec\b|\bedhec\b"
    r"|hec paris|\bhec\b(?= ))",
    re.I,
)


UNDERGRAD_SCHOOLS_RE = re.compile(
    # ── Ivy League ──
    r"harvard university|yale university|princeton university|columbia university|"
    r"university of pennsylvania|\bdartmouth\b|cornell university|brown university|"
    # ── MIT / Stanford / Chicago tier ──
    r"\bmit\b|massachusetts institute of technology|stanford university|"
    r"university of chicago|duke university|northwestern university|"
    r"johns hopkins|california institute of technology|\bcaltech\b|"
    # ── Top private research universities ──
    r"vanderbilt university|rice university|notre dame|wake forest university|"
    r"tufts university|emory university|georgetown university|"
    r"boston college|boston university|"
    r"university of southern california|"
    r"new york university|\bnyu\b|carnegie mellon|"
    r"lehigh university|case western|tulane university|"
    r"george washington university|american university|"
    r"rensselaer polytechnic|worcester polytechnic|"
    r"fordham university|villanova university|"
    r"santa clara university|loyola university|"
    r"university of miami|syracuse university|"
    r"drexel university|temple university|"
    r"pepperdine university|gonzaga university|"
    r"marquette university|depaul university|"
    r"seton hall|fairfield university|"
    # ── Top liberal arts colleges ──
    r"amherst college|williams college|swarthmore college|wellesley college|"
    r"bowdoin college|middlebury college|pomona college|carleton college|"
    r"hamilton college|colgate university|colby college|bates college|"
    r"vassar college|barnard college|smith college|mount holyoke|"
    r"trinity college|davidson college|haverford college|"
    r"claremont mckenna|harvey mudd|scripps college|"
    r"lafayette college|bucknell university|dickinson college|"
    r"wesleyan university|oberlin college|grinnell college|"
    r"macalester college|colorado college|union college|"
    r"kenyon college|denison university|rhodes college|"
    r"furman university|centre college|connecticut college|"
    r"holy cross|university of richmond|"
    r"bryn mawr|sarah lawrence|"
    r"skidmore college|hobart and william smith|"
    r"gettysburg college|franklin & marshall|"
    r"reed college|whitman college|"
    # ── Top public universities ──
    r"university of michigan|university of virginia|university of north carolina|"
    r"university of california|uc berkeley|ucla|uc san diego|uc davis|"
    r"uc santa barbara|uc irvine|uc santa cruz|uc riverside|uc merced|"
    r"university of texas|university of florida|university of georgia|"
    r"university of illinois|university of wisconsin|university of washington|"
    r"university of maryland|penn state|pennsylvania state|ohio state|"
    r"purdue university|michigan state|indiana university|"
    r"university of minnesota|university of iowa|university of colorado|"
    r"university of arizona|arizona state university|florida state university|"
    r"virginia tech|georgia tech|georgia institute of technology|"
    r"university of pittsburgh|university of connecticut|uconn|"
    r"university of delaware|university of maine|university of new hampshire|"
    r"university of vermont|university of rhode island|"
    r"university of massachusetts|umass|rutgers university|"
    r"stony brook university|binghamton university|"
    r"university at buffalo|university at albany|"
    r"university of cincinnati|ohio university|miami university|"
    r"university of dayton|university of kentucky|university of tennessee|"
    r"university of alabama|auburn university|"
    r"university of mississippi|ole miss|"
    r"university of arkansas|university of oklahoma|oklahoma state|"
    r"university of kansas|kansas state|"
    r"university of missouri|university of nebraska|"
    r"iowa state university|university of north dakota|north dakota state|"
    r"university of wyoming|university of idaho|boise state|"
    r"university of nevada|university of new mexico|new mexico state|"
    r"university of utah|utah state|brigham young|\bbyu\b|"
    r"university of hawaii|university of alaska|"
    r"university of south carolina|clemson university|"
    r"north carolina state|\bnc state\b|"
    r"william & mary|college of william and mary|"
    r"james madison university|virginia commonwealth|"
    r"louisiana state|\blsu\b|"
    # ── HBCUs ──
    r"howard university|morehouse college|spelman college|hampton university|"
    r"tuskegee university|fisk university|xavier university of louisiana|"
    r"north carolina a&t|morgan state|clark atlanta|"
    # ── Military academies ──
    r"west point|united states military academy|"
    r"naval academy|united states naval academy|"
    r"air force academy|united states air force academy|"
    r"coast guard academy|merchant marine academy|"
    # ── Other notable US schools ──
    r"babson college|bentley university|"
    r"rochester institute|university of rochester|"
    r"elon university|high point university|university of denver|"
    r"university of san diego|university of san francisco|"
    r"seattle university|willamette university|"
    r"cal poly|california polytechnic|"
    r"california state|cal state|"
    r"florida international|university of central florida|\bucf\b|"
    r"university of south florida|florida institute of technology|"
    r"rollins college|stetson university|"
    # ── Canada ──
    r"university of toronto|university of british columbia|mcgill university|"
    r"queen's university|western university|university of western ontario|"
    r"university of waterloo|university of alberta|university of calgary|"
    r"dalhousie university|university of ottawa|simon fraser university|"
    r"concordia university|york university|university of victoria|"
    r"university of manitoba|"
    # ── UK & Ireland ──
    r"university of oxford|oxford university|"
    r"university of cambridge|cambridge university|"
    r"imperial college|university college london|\bucl\b|"
    r"london school of economics|\blse\b|"
    r"king's college london|queen mary university|"
    r"university of edinburgh|university of glasgow|"
    r"university of manchester|university of bristol|"
    r"university of birmingham|university of leeds|"
    r"university of nottingham|university of sheffield|"
    r"university of warwick|university of exeter|"
    r"durham university|lancaster university|"
    r"university of bath|university of york|"
    r"university of st andrews|heriot-watt|"
    r"trinity college dublin|university college dublin|"
    # ── Europe ──
    r"sciences po|école polytechnique|\bpolytechnique\b|"
    r"ecole normale superieure|"
    r"leiden university|delft university|"
    r"university of amsterdam|vrije universiteit|"
    r"erasmus university|tilburg university|"
    r"lund university|stockholm university|"
    r"norwegian school of economics|\bnhh\b|"
    r"bocconi university|"
    r"tu munich|technical university munich|"
    r"humboldt university|"
    r"university of zurich|eth zurich|"
    r"university of geneva|\bepfl\b|"
    # ── Asia / Oceania / Other ──
    r"indian institute of technology|\biit\b(?! tower)|"
    r"indian institute of management|\biim\b|"
    r"national university of singapore|\bnus\b|"
    r"nanyang technological|"
    r"university of hong kong|\bhku\b|"
    r"chinese university of hong kong|"
    r"hong kong university of science|\bhkust\b|"
    r"peking university|tsinghua university|fudan university|"
    r"university of tokyo|kyoto university|waseda university|keio university|"
    r"seoul national university|yonsei university|korea university|"
    r"australian national university|\banu\b|"
    r"university of melbourne|university of sydney|"
    r"university of queensland|monash university|"
    r"university of new south wales|\bunsw\b|"
    # ── Middle East / Africa ──
    r"american university of beirut|"
    r"american university in cairo|"
    r"university of cape town|stellenbosch university",
    re.I,
)


def _parse_json(val):
    if not val or (isinstance(val, float)):
        return []
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _detect_mbb_firm(company: str, company_id: str = "") -> str | None:
    for firm, pat in MBB_PATTERNS.items():
        if pat.search(company) or (company_id and pat.search(company_id)):
            return firm
    return None


def _clean_date(val) -> str | None:
    if not val or (isinstance(val, float)):
        return None
    s = str(val).strip()
    return s if s else None


def _extract_education(edu_list: list) -> dict:
    """Return school/year/start_year for each degree type."""
    result = {
        "mba_school": None, "mba_year": None, "mba_start_year": None,
        "ms_school": None, "ms_year": None, "ms_start_year": None,
        "phd_school": None, "phd_year": None, "phd_start_year": None,
        "jd_school": None, "jd_year": None, "jd_start_year": None,
        "undergrad_school": None, "undergrad_year": None, "undergrad_start_year": None,
    }

    undergrad_candidates = []

    for edu in edu_list:
        title = (edu.get("title") or "").strip()
        degree = (edu.get("degree") or "").strip()
        field = (edu.get("field") or "").strip()
        end_year_raw = edu.get("end_year") or ""
        start_year_raw = edu.get("start_year") or ""

        # Extract 4-digit years
        m = re.search(r"\d{4}", str(end_year_raw))
        end_year = m.group() if m else None
        m = re.search(r"\d{4}", str(start_year_raw))
        start_year = m.group() if m else None
        year = end_year or start_year  # graduation year preferred

        is_mba = (
            MBA_KEYWORDS.search(degree)
            or MBA_KEYWORDS.search(field)
            or MBA_SCHOOLS.search(title)
        )
        is_phd = PHD_KEYWORDS.search(degree) or PHD_KEYWORDS.search(field)
        is_jd = JD_KEYWORDS.search(degree) or JD_KEYWORDS.search(field)
        is_ms = not is_mba and not is_phd and not is_jd and (
            MS_KEYWORDS.search(degree) or MS_KEYWORDS.search(field)
        )

        if is_phd and not result["phd_school"]:
            result["phd_school"] = title
            result["phd_year"] = year
            result["phd_start_year"] = start_year or year
        elif is_jd and not result["jd_school"]:
            result["jd_school"] = title
            result["jd_year"] = year
            result["jd_start_year"] = start_year or year
        elif is_mba and not result["mba_school"]:
            result["mba_school"] = title
            result["mba_year"] = year
            result["mba_start_year"] = start_year or year
        elif is_ms and not result["ms_school"]:
            result["ms_school"] = title
            result["ms_year"] = year
            result["ms_start_year"] = start_year or year
        else:
            # Capture even untitled entries — they still represent an education period
            undergrad_candidates.append((title, year, start_year))

    # LinkedIn education is newest-first, so last = oldest.
    # P1: oldest entry on known-university list (avoids picking high schools)
    # P2: oldest named entry (lesser-known school not in list)
    # P3: oldest any entry (year-only placeholder)
    if undergrad_candidates:
        p1 = [(t, y, sy) for t, y, sy in undergrad_candidates if t and UNDERGRAD_SCHOOLS_RE.search(t)]
        p2 = [(t, y, sy) for t, y, sy in undergrad_candidates if t]
        t, y, sy = (p1 or p2 or undergrad_candidates)[-1]
        result["undergrad_school"] = t or None
        result["undergrad_year"] = y
        result["undergrad_start_year"] = sy or y

    return result


def _extract_experiences(exp_list: list) -> tuple[list[dict], bool, list[str], dict | None, str | None, str | None]:
    """Parse experience entries, detect MBB.

    Returns (exps, has_mbb, mbb_firms, primary_mbb, post_mbb_company, post_mbb_title).
    primary_mbb is the first (oldest) real (non-intern) MBB experience dict.
    post_mbb_company/title is the role immediately after that first stint.
    """
    exps = []
    mbb_firms_found: set[str] = set()

    for exp in exp_list:
        has_company = bool(exp.get("company"))
        company = (exp.get("company") or exp.get("title") or "").strip()
        company_id = str(exp.get("company_id") or "").strip()
        # For simple entries: job title is in "title" when "company" is set, else "subtitle"
        if has_company:
            title = (exp.get("subtitle") or exp.get("title") or "").strip()
        else:
            title = (exp.get("subtitle") or "").strip()
        start = _clean_date(exp.get("start_date"))
        end = _clean_date(exp.get("end_date"))

        # positions sub-array (grouped roles)
        positions = exp.get("positions") or []
        all_titles = []

        if positions:
            for pos in positions:
                t = (pos.get("title") or pos.get("subtitle") or "").strip()
                if t:
                    all_titles.append(t)
            if not title and all_titles:
                title = all_titles[0]
            # positions are newest-first; oldest start = last position, latest end = first position
            if not start:
                for pos in reversed(positions):
                    s = _clean_date(pos.get("start_date"))
                    if s:
                        start = s
                        break
            if not end:
                for pos in positions:
                    e = _clean_date(pos.get("end_date"))
                    if e:
                        end = e
                        break
        else:
            if title:
                all_titles.append(title)

        firm = _detect_mbb_firm(company, company_id)
        if firm:
            mbb_firms_found.add(firm)

        exps.append(
            {
                "company": company or None,
                "title": title or None,
                "all_titles": "; ".join(all_titles) if all_titles else None,
                "start": start,
                "end": end,
                "is_mbb": 1 if firm else 0,
                "mbb_firm": firm,
            }
        )

    has_mbb = bool(mbb_firms_found)

    # Find the first (oldest) real MBB stint — exps[0] = most recent (LinkedIn order)
    primary_mbb: dict | None = None
    post_mbb_company: str | None = None
    post_mbb_title: str | None = None

    for i in range(len(exps) - 1, -1, -1):  # scan oldest → newest
        exp = exps[i]
        if not exp["is_mbb"]:
            continue
        titles_text = (exp["all_titles"] or "") + " " + (exp["title"] or "") + " " + (exp["company"] or "")
        if INTERN_RE.search(titles_text):
            continue  # skip internships / fellowships / programs
        primary_mbb = exp
        if i > 0:
            # Scan forward (lower index = more recent) skipping intern/MBA/admin roles
            for j in range(i - 1, -1, -1):
                nxt = exps[j]
                nxt_check = (nxt["all_titles"] or "") + " " + (nxt["title"] or "") + " " + (nxt["company"] or "")
                if not INTERN_RE.search(nxt_check):
                    post_mbb_company = nxt["company"]
                    all_ti = nxt["all_titles"] or ""
                    parts = [t.strip() for t in all_ti.split(";") if t.strip()]
                    post_mbb_title = parts[-1] if parts else nxt["title"]
                    break
        break

    return exps, has_mbb, sorted(mbb_firms_found), primary_mbb, post_mbb_company, post_mbb_title


def clean(input_file: str, output_csv: str) -> int:
    ext = os.path.splitext(input_file)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file, low_memory=False)
    print(f"  Read {len(df):,} rows from {input_file}")

    rows = []
    max_exp = 0

    for _, row in df.iterrows():
        edu_list = _parse_json(row.get("education"))
        exp_list = _parse_json(row.get("experience"))

        edu = _extract_education(edu_list)
        exps, has_mbb, mbb_firms, primary_mbb, post_mbb_company, post_mbb_title = _extract_experiences(exp_list)

        max_exp = max(max_exp, len(exps))

        # Detect profiles where every titled experience is intern/student-level
        titled_exps = [e for e in exps if e["title"] or e["all_titles"]]
        all_intern_profile = len(titled_exps) == 0 or all(
            INTERN_RE.search((e["all_titles"] or "") + " " + (e["title"] or ""))
            for e in titled_exps
        )
        if all_intern_profile:
            continue

        # location: prefer 'location' col, fall back to city+country
        location = str(row.get("location") or "").strip()
        if not location:
            city = str(row.get("city") or "").strip()
            country = str(row.get("country_code") or "").strip()
            location = ", ".join(filter(None, [city, country]))

        current_company = str(row.get("current_company_name") or row.get("current_company") or "").strip() or None
        current_title = str(row.get("position") or "").strip() or None

        r: dict = {
            "profile_id": str(row.get("id") or row.get("linkedin_id") or "").strip(),
            "name": str(row.get("name") or "").strip() or None,
            "location": location or None,
            "current_title": current_title,
            "current_company": current_company,
            "mba_school": edu["mba_school"],
            "mba_year": edu["mba_year"],
            "mba_start_year": edu["mba_start_year"],
            "ms_school": edu["ms_school"],
            "ms_year": edu["ms_year"],
            "ms_start_year": edu["ms_start_year"],
            "phd_school": edu["phd_school"],
            "phd_year": edu["phd_year"],
            "phd_start_year": edu["phd_start_year"],
            "jd_school": edu["jd_school"],
            "jd_year": edu["jd_year"],
            "jd_start_year": edu["jd_start_year"],
            "undergrad_school": edu["undergrad_school"],
            "undergrad_year": edu["undergrad_year"],
            "undergrad_start_year": edu["undergrad_start_year"],
            "has_mbb": 1 if has_mbb else 0,
            "mbb_firms": ", ".join(mbb_firms) if mbb_firms else None,
            "mbb_company": primary_mbb["company"] if primary_mbb else None,
            "mbb_firm": primary_mbb["mbb_firm"] if primary_mbb else None,
            "mbb_title": primary_mbb["title"] if primary_mbb else None,
            "mbb_start": primary_mbb["start"] if primary_mbb else None,
            "mbb_end": primary_mbb["end"] if primary_mbb else None,
            "post_mbb_company": post_mbb_company,
            "post_mbb_title": post_mbb_title,
        }

        for i, exp in enumerate(exps, 1):
            r[f"exp_{i}_company"] = exp["company"]
            r[f"exp_{i}_title"] = exp["title"]
            r[f"exp_{i}_all_titles"] = exp["all_titles"]
            r[f"exp_{i}_start"] = exp["start"]
            r[f"exp_{i}_end"] = exp["end"]
            r[f"exp_{i}_is_mbb"] = exp["is_mbb"]
            r[f"exp_{i}_mbb_firm"] = exp["mbb_firm"]

        rows.append(r)

    out = pd.DataFrame(rows)

    # Drop MBB-flagged profiles where all MBB roles were internships/externships
    # (has_mbb=1 but primary_mbb was never set, so mbb_company is null)
    intern_only_mask = (out["has_mbb"] == 1) & out["mbb_company"].isna()
    intern_only_count = intern_only_mask.sum()
    out = out[~intern_only_mask]

    # Drop MBB profiles with no post-MBB path (still at MBB or data gap)
    no_post_mbb_mask = (out["has_mbb"] == 1) & out["post_mbb_company"].isna()
    no_post_mbb_count = no_post_mbb_mask.sum()
    out = out[~no_post_mbb_mask]

    out.to_csv(output_csv, index=False)
    mbb_count = out["has_mbb"].sum() if "has_mbb" in out.columns else 0
    mba_count = out["mba_school"].notna().sum() if "mba_school" in out.columns else 0
    ms_count = out["ms_school"].notna().sum() if "ms_school" in out.columns else 0
    phd_count = out["phd_school"].notna().sum() if "phd_school" in out.columns else 0
    jd_count = out["jd_school"].notna().sum() if "jd_school" in out.columns else 0
    named_count = out["name"].notna().sum() if "name" in out.columns else 0
    print(f"  Dropped (intern-only MBB):  {intern_only_count:,}")
    print(f"  Dropped (no post-MBB path): {no_post_mbb_count:,}")
    print(f"  Wrote {len(out):,} rows → {output_csv}  (max {max_exp} experience slots)")
    print(f"  Profiles with name:        {named_count:,}")
    print(f"  Profiles with MBB exp:     {mbb_count:,}")
    print(f"  Profiles with MBA:         {mba_count:,}")
    print(f"  Profiles with MS/MA/MEng:  {ms_count:,}")
    print(f"  Profiles with PhD:         {phd_count:,}")
    print(f"  Profiles with JD:          {jd_count:,}")
    return len(out)


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else "LinkedIn people profiles.xlsx"
    out = sys.argv[2] if len(sys.argv) > 2 else "cleaned_profiles.csv"
    clean(inp, out)
