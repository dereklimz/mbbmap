# 🗺️ MBBMap

Where do McKinsey, BCG and Bain consultants go next? MBBMap takes 621 real career histories of MBB alumni, tags every role, and shows each person's path **before, during and after** consulting, grouped into exit archetypes: founders, investors, big tech, product, strategy & ops and more.

## Features

- **Career path cards.** Each profile is a timeline: undergrad → pre-MBB roles → MBB stint → exit → current role. MBB stints are color-coded by firm.
- **Exit archetype filters.** One click to see everyone whose first move after MBB was Founder, PE / Investing, MAANG, Big Tech, Startups, Product Management, Strategy & Ops or Consulting.
- **Degree breakdown.** MBA, MS/MA, PhD and JD counts across the cohort.
- **Industry and role tags.** Each person's current role is tagged by industry and function.
- **No API key needed.** Clone it and run it.

## Data

| | |
|---|---|
| Source | LinkedIn profiles from [Bright Data](https://brightdata.com), filtered to people with McKinsey, BCG or Bain experience, US-based, pulled March 2026 |
| Raw profiles | 830 |
| Final cohort | **621** MBB alumni (McKinsey 273 · BCG 208 · Bain 140) |
| Advanced degrees | MBA 261 · MS/MA 23 · PhD 13 · JD 3 |
| Most common first exit | Google |

**Privacy:** names and LinkedIn identifiers are removed, and profile IDs are replaced with random pseudonyms (`person-0001` …). The raw dataset is not included in this repo.

## Method

The core problem: LinkedIn data is messy, nested and inconsistent. To answer *"where do MBB consultants go next?"* every profile needs a clear **pre-MBB → MBB → post-MBB** structure. The pipeline gets there in four steps.

### 1. Clean: flatten the raw profiles
`clean_profiles.py` parses each profile's nested JSON experience and education into one row per person.
- **Grouped roles.** LinkedIn nests multiple roles at one company (e.g. Associate → Engagement Manager at McKinsey). These are merged into a single stint, keeping every title and taking the earliest start and latest end date.
- **Chronology.** LinkedIn lists newest first, so the pipeline keeps that order (`exp_1` = most recent) and reads it oldest → newest when building the path.
- **Location** falls back from city to city + country when missing.

### 2. Tag: label MBB status and education
- **MBB detection.** Each employer is matched against firm patterns: `McKinsey`, `Boston Consulting` / `BCG`, and `Bain` but **not Bain Capital** (a PE firm, excluded with a negative lookahead). The LinkedIn company ID is checked too, for cases where the company name is blank.
- **Internship filter.** Summer associates, interns, fellows, co-ops and diversity/insight programs (e.g. *BCG RISE*, *pre-MBA*) are flagged, so a summer at McKinsey doesn't count as an MBB career.
- **Degree classification.** Each education entry is tagged MBA / MS / PhD / JD from the degree name, the field of study, and a list of ~90 named business schools plus generic patterns like "school of business" (so "Wharton School" counts as an MBA even if the degree field is empty).
- **Undergrad detection.** The oldest entry that matches a list of ~330 known universities is used, which avoids picking up high schools. It falls back to the oldest named entry.

### 3. Anchor: find the pre vs. post split
- **Primary MBB stint:** the *first* non-intern role at an MBB firm. Everything before it is **pre-MBB**; everything after it is **post-MBB**.
- **First exit:** the next non-intern role after that stint. This is the move that defines the person's archetype.

### 4. Filter and classify
| Step | Profiles |
|---|---|
| Raw dataset | 830 |
| Removed: no real work history (all intern/student roles) | −3 |
| Removed: MBB experience was internship-only | −139 |
| Removed: still at MBB / no post-MBB move yet | −59 |
| Removed: duplicate profiles | −7 |
| Removed: no MBB role found | −1 |
| **Final cohort** | **621** |

Each person's first exit is then assigned to **exactly one** archetype (mutually exclusive, checked in priority order): Founder → PE / Investing → MAANG → Big Tech → Startups → Product Management → Strategy & Ops → Consulting → Other. Founder is based on title; PE, MAANG and Big Tech on the company; PM and Strategy & Ops on title.

## Architecture

```
Bright Data CSV ──► clean_profiles.py ──► redact_profiles.py ──► data_loader.py ──► SQLite ──► app.py
   (raw)             clean + tag + anchor    strip names / IDs       load + query                (Streamlit UI)
```

| File | Role |
|---|---|
| `clean_profiles.py` | Steps 1–4: parse, tag MBB and degrees, find pre/post split, filter |
| `redact_profiles.py` | Removes names and identifiers, de-duplicates, keeps MBB alumni only, assigns pseudonyms |
| `data_loader.py` | Loads the CSV into SQLite and provides the query helpers |
| `app.py` | Streamlit UI: archetype classification, path cards, filters |

## Getting started

```bash
git clone https://github.com/dereklimz/mbbmap.git
cd mbbmap
pip install -r requirements.txt
streamlit run app.py
```

The database builds itself from `profiles_redacted.csv` on first run.

## Limitations

- **Rule-based tagging.** Titles and companies are matched with regex, so unusual titles can land in "Other".
- **Self-reported data.** Dates and titles are whatever people put on LinkedIn.
- **Sample, not census.** The cohort reflects how the source dataset was filtered, not all MBB alumni (US-based profiles only, as of March 2026).

## Tech stack

Python · pandas · regex · SQLite · Streamlit
