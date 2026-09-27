"""
app.py — MBBMap  ·  Career Path Archetypes
Dark-themed, card-based UI showing career journeys of MBB alumni.
"""

import os
import re
from html import escape

import anthropic
import pandas as pd
import streamlit as st

from data_loader import DB_PATH, get_max_exp, get_summary_stats, load_csv, query_profiles

# ── config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MBBMap",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Build the database on first run: full local data if present, else the redacted public set
if not os.path.exists(DB_PATH):
    load_csv("cleaned_profiles.csv" if os.path.exists("cleaned_profiles.csv") else "profiles_redacted.csv")

FIRM_COLOR   = {"McKinsey": "#00A9E0", "BCG": "#00854A", "Bain": "#CC0000"}
FIRM_BG      = {"McKinsey": "#003a52", "BCG": "#0d3a20", "Bain": "#3a0d0d"}
DEST_COLOR   = "#FF9900"
DEST_BG      = "#2a1a00"

MBB_RE = re.compile(r"mckinsey|boston consulting|bcg\b|bain & company|\bbain\b(?! capital)", re.I)

# ── archetype detection regexes ────────────────────────────────────────────────
MAG7_RE = re.compile(
    r"\bgoogle\b|alphabet|\byoutube\b|\bamazon\b|\bapple\b|\bmicrosoft\b|"
    r"\bnvidia\b|\btesla\b|\bmeta\b|facebook|\binstagram\b|\bwhatsapp\b", re.I)
# Keep alias so industry-pill code still works
MAANG_RE = MAG7_RE

MBB_CURRENT_RE = re.compile(
    r"mckinsey|boston consulting|\bbcg\b|bain & company|\bbain\b(?! capital)", re.I)

# Investment banks / bulge-bracket / boutique IB + asset managers only (not retail banks)
IB_RE = re.compile(
    r"goldman sachs|j\.?p\.?\s*morgan|jpmorgan|morgan stanley|"
    r"lazard|evercore|centerview|moelis|jefferies|rothschild|"
    r"barclays|\bubs\b|deutsche bank|nomura|\bbaird\b|stifel|piper sandler|"
    r"brown brothers harriman|bernstein|blackrock|wellington management|"
    r"mfs investment|\bbny\b|s&p global|citadel|\blpl financial\b|"
    r"duff & phelps|houlihan lokey|harris williams", re.I)

PE_VC_RE = re.compile(
    r"private equity|venture capital|blackstone|kkr|carlyle|apollo|warburg|"
    r"bain capital|tpg|sequoia|andreessen|a16z|accel|benchmark|kleiner|bessemer|"
    r"lightspeed|greylock|general atlantic|silver\s*lake|thoma bravo|"
    r"insight partners|general catalyst|index ventures|charlesbank|"
    r"family office|tailwind capital|aea investors|audax|francisco partners|"
    r"vista equity|advent international|cerberus|oaktree|ares management|"
    r"blue owl|hg capital|permira|\bapax\b|cinven|"
    r"elliott investment|pzena investment|harbourvest|"
    r"shore capital partners|nonantum capital|capital group\b|"
    r"riot ventures|partners group\b|kohler ventures|"
    r"qualcomm ventures|angeles investors|union park capital|"
    r"holocene advisors|alphataraxia|golden capital markets|"
    r"falfurrias|hidden river group|jordan park group|"
    r"aspen standard wealth|focus partners wealth|"
    r"geometric wealth|tuck social venture|"
    r"michigan climate venture|nuimpact|"
    r"gladstone capital|flexpoint ford|rubicon technology partners", re.I)

CONSULTING_TITLE_RE = re.compile(
    r"\bconsultant\b|engagement manager|associate.*consultant|"
    r"strategy consultant|management consultant", re.I
)

CONSULTING_RE = re.compile(
    r"\bpwc\b|pricewaterhousecoopers|deloitte|\baccenture\b|ernst & young|ey-parthenon|"
    r"\bkpmg\b|oliver wyman|analysis group|spencer stuart|\bghsmart\b|simon.kucher|"
    r"altman solon|l\.?e\.?k\.|roland berger|booz allen|west monroe|"
    r"\bgartner\b|korn ferry|alvarez.*marsal|riveron|clarity\b|"
    r"bridgespan|strategy&|strategy and|huron consulting|"
    r"bcg x\b|mckinsey.*ventures|mckinsey.*implementation|mckinsey.*digital|"
    r"alixpartners|fti consulting|\bkearney\b|brattle group|\bteneo\b|"
    r"heidrick.struggles|alphaSights|escalent|edelman\b|\bomnicom\b|ogilvy\b|"
    r"vayner|alphasights|russell reynolds|morganfranklin|guidehouse|forrester research", re.I)

ENTERPRISE_TECH_RE = re.compile(
    # ── Listed public tech (NASDAQ / S&P 500), not in Mag 7 ──
    r"\blinkedin\b|\btiktok\b|\bnetflix\b|"
    r"\bsalesforce\b|atlassian|servicenow|adobe\b|intuit\b|\bdell\b|t-mobile|"
    r"palo alto networks|\bsap\b|\boracle\b|\bcisco\b|workday|snowflake|"
    r"\bpalantir\b|\bspotify\b|\bairbnb\b|\buber\b|\blyft\b|\bshopify\b|\bfujitsu\b|\bquantcast\b|"
    r"\btwilio\b|\bdatadog\b|crowdstrike|\bzendesk\b|hubspot|"
    r"\bdoordash\b|\binstacart\b|"
    r"siemens\b|coinbase|\bcognizant\b|broadridge|"
    r"pure storage|\bfastly\b|\bpagaya\b|doubleverify", re.I)

AI_CO_RE = re.compile(
    r"\bopenai\b|anthropic|\bcohere\b|mistral|stability ai|character\.?ai|"
    r"scale ai|hugging face|perplexity|inflection ai|adept ai|\bgroq\b|"
    r"together ai|imbue|\bai21\b|aleph alpha|deepmind|xai\b|"
    r"norm\s*ai|c3\s*ai|cognition\b|abridge\b|commure|keystone ai|"
    r"center for ai safety|ai safety", re.I)

# Growth-stage / private tech companies (not listed on NASDAQ / S&P 500)
STARTUP_RE = re.compile(
    # ── Moved from Big Tech (private) ──
    r"anduril|\bstripe\b|\bopensignal\b|\bfaire\b|\bmews\b|\bdeel\b|"
    r"bloomberg|\bformlabs\b|\bverkada\b|"
    # ── Named private / growth-stage companies ──
    r"norm\s*ai\b|c3\s*ai\b|entrata|\bshibumi\b|\bhalcyon\b|"
    r"datavant|drfirst|commure|instawork|charge robotics|\bagero\b|"
    r"\bcribl\b|\bdruva\b|\bcyera\b|appomni|\bnuro\b|deepfield|"
    r"chiefclouds|keystone ai|keyway\b|mercor\b|circleback\b|"
    r"abridge\b|\beliza\b|cognition\b|prosper ai|tools for humanity|"
    r"waymark\b|\bplaid\b|\bviran\b|\bpebl\b|spuree\b|\bsway\b|"
    r"relate\b|validyn\b|euna solutions|\blensa\b|\bdili\b|"
    r"covista\b|eidra\b|memori\b|pelago\b", re.I)

HEALTHCARE_RE = re.compile(
    r"\bamgen\b|regeneron|novo nordisk|pfizer|moderna|johnson.johnson|abbvie|"
    r"cvs health|\boptum\b|unitedhealth|humana|astrazeneca|roche|novartis|"
    r"eli lilly|bristol.myers|\bmerck\b|biogen|gilead|vertex|"
    r"recursion|radiology partners|elevance|cigna|anthem|solventum|"
    r"kaiser|cleveland clinic|mayo clinic|dentive|"
    r"sanofi|\btakeda\b|\bbayer\b|thermo fisher|boston scientific|zimmer biomet|"
    r"edwards lifesciences|davita|northwell|\bcentene\b|oak street health|"
    r"adventhealth|barnes.jewish|quantum health|acentra health|"
    r"mount auburn hospital|paralign health|tenet healthcare|"
    r"duke.*health|mgh.*martinos|cha hollywood presbyterian|"
    r"merus\b|wave life sciences|complete genomics|"
    r"ten.?zero bio|kite pharma|\bsobi\b|glaukos|caris life|\bmedica\b", re.I)

CONSUMER_RE = re.compile(
    r"\bmcdonald|pepsi|coca.cola|unilever|procter.gamble|\bp&g\b|hershey|"
    r"home depot|walmart|target\b|costco|nike\b|adidas|lvmh|"
    r"\bvisa\b|mastercard|american greetings|abbyson|"
    r"pepsico|disney\b|warner|comcast|verizon|at&t\b", re.I)

GOVT_NONPROFIT_RE = re.compile(
    r"world bank|imf\b|united nations|\bun\b |government|federal reserve|"
    r"state department|department of|metropolitan transportation|"
    r"american institutes for research|\bifpri\b|non.?profit|"
    r"theodore payne|japanese consulate|usta\b|american institute|"
    r"\bfoundation\b|\binstitute\b", re.I)

ACADEMIA_RE = re.compile(
    r"university of|\.edu\b| university$| college$|school of medicine|"
    r"harvard business school|mit sloan|wharton school|stanford.*school|"
    r"columbia business school|johns hopkins|james madison university", re.I)

FOUNDER_TITLE_RE = re.compile(r"\bfounder\b|co-founder|cofounder", re.I)
FOUNDER_CO_RE    = re.compile(r"\bfreelance\b|self.employed|\bindependent\b|stealth startup|stealth\b", re.I)
MBA_NOW_RE       = re.compile(r"mba candidate|mba student|mba class of", re.I)

PM_TITLE_RE = re.compile(
    r"product manager\b|product management\b|head of product\b|"
    r"vp[, ]+(?:of )?product\b|vp[, ]+(?:of )?products\b|"
    r"director[, ]+(?:of )?product\b|director[, ]+(?:of )?products\b|"
    r"chief product officer|\bchief product\b|"
    r"product lead\b|product owner\b|"
    r"group product manager|\bgpm\b", re.I)

STRATEGY_OPS_TITLE_RE = re.compile(
    r"\bstrategy\b|business operations|\bbiz ops\b|"
    r"chief of staff|\bcos\b|general manager|\bgm\b|"
    r"head of operations|head of.*ops|vp.*operations|vp.*strategy|"
    r"director.*strategy|director.*operations|"
    r"product strategy|product planning|commercial strategy", re.I)

INVESTING_TITLE_RE = re.compile(
    r"\binvestor\b|investment.*associate|investment.*analyst|"
    r"portfolio company|principal.*invest|associate.*private equity|"
    r"associate.*venture|growth.*equity|"
    r"\bmanaging partner\b|\bgeneral partner\b", re.I)

# ── destination definitions: label → match fn(co, ti) ─────────────────────────
# ── Exit categories (MECE, evaluated in priority order) ───────────────────────
# Each profile is assigned exactly ONE category based on their first exit after MBB.
EXIT_CATEGORIES = [
    ("Founder",            lambda co, ti: bool(FOUNDER_TITLE_RE.search(ti))),
    ("PE / Investing",     lambda co, ti: bool(IB_RE.search(co)) or bool(PE_VC_RE.search(co)) or bool(INVESTING_TITLE_RE.search(ti))),
    ("MAANG",      lambda co, ti: bool(MAG7_RE.search(co))),
    ("Big Tech",           lambda co, ti: bool(ENTERPRISE_TECH_RE.search(co))),
    ("Startups",           lambda co, ti: bool(STARTUP_RE.search(co)) or bool(AI_CO_RE.search(co))),
    ("Product Management", lambda co, ti: bool(PM_TITLE_RE.search(ti))),
    ("Strategy & Ops",     lambda co, ti: bool(STRATEGY_OPS_TITLE_RE.search(ti))),
    ("Consulting",         lambda co, ti: bool(CONSULTING_RE.search(co)) or bool(MBB_COMPANY_RE.search(co))),
]
EXIT_CATEGORY_LABELS = [label for label, _ in EXIT_CATEGORIES]

def _classify_exit(exit_co: str, exit_ti: str) -> str:
    """Assign exactly one exit category (MECE) based on first post-MBB role."""
    exit_co, exit_ti = exit_co or "", exit_ti or ""
    for label, fn in EXIT_CATEGORIES:
        if fn(exit_co, exit_ti):
            return label
    return "Other"

MBB_COMPANY_RE = re.compile(
    r"mckinsey|boston consulting|\bbcg\b|bain & company|\bbain\b(?! capital)", re.I)

_INTERN_TITLE_RE = re.compile(
    r"\bintern(ship)?\b|\bfellow(ship)?\b|\bco-?op\b|\bsummer\b|\bstudent\b|"
    r"forward program|bcg rise|\bpre-?mba\b|leadership program|"
    r"diversity program|insight program|immersion program|"
    r"\bcandidate\b|postdoctoral|\badministrative assistant\b", re.I
)

def _get_primary_exit(row, max_exp: int) -> tuple[str, str]:
    """Scan oldest→newest; find first real (non-intern) MBB stint; return the role right after."""
    for i in range(max_exp, 0, -1):  # exp_N = oldest, exp_1 = most recent
        co = row.get(f"exp_{i}_company") or ""
        is_mbb = row.get(f"exp_{i}_is_mbb") or 0
        if not (is_mbb or MBB_COMPANY_RE.search(co)):
            continue
        titles = str(row.get(f"exp_{i}_all_titles") or row.get(f"exp_{i}_title") or "") + " " + co
        if _INTERN_TITLE_RE.search(titles):
            continue  # skip internships / fellowships / programs
        # Found the first real MBB stint; exit is the more-recent role (lower index)
        exit_idx = i - 1
        if exit_idx < 1:
            return "", ""  # still at MBB (exp_1 is this MBB)
        exit_co = row.get(f"exp_{exit_idx}_company") or ""
        # Use the oldest/entry title (last in newest-first all_titles list)
        all_ti = str(row.get(f"exp_{exit_idx}_all_titles") or "").strip()
        if all_ti:
            parts = [t.strip() for t in all_ti.split(";") if t.strip()]
            exit_ti = parts[-1] if parts else str(row.get(f"exp_{exit_idx}_title") or "")
        else:
            exit_ti = str(row.get(f"exp_{exit_idx}_title") or "")
        return exit_co, exit_ti
    return "", ""

DESTINATIONS = {"All": None, **{k: k for k in EXIT_CATEGORY_LABELS}, "Other": "other"}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── global dark theme ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #0b1220 !important;
    color: #d0dcea !important;
}
[data-testid="stSidebar"] { background: #0b1220 !important; }
[data-testid="block-container"] { padding-top: 1.5rem !important; }

/* ── metric cards ── */
[data-testid="stMetric"] {
    background: #111c2d;
    border: 1px solid #1e2d42;
    border-radius: 12px;
    padding: 18px 20px !important;
}
[data-testid="stMetricLabel"] p { color: #7a9bb5 !important; font-size: 13px !important; }
[data-testid="stMetricValue"] { color: #e8f0f8 !important; font-size: 32px !important; font-weight: 700 !important; }

/* ── tabs ── */
[data-testid="stTabs"] button {
    background: #111c2d !important;
    color: #7a9bb5 !important;
    border-radius: 8px !important;
    border: 1px solid #1e2d42 !important;
    margin-right: 6px !important;
    font-size: 13px !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    background: #1e3a5f !important;
    color: #60b4ff !important;
    border-color: #2c5282 !important;
}
[data-testid="stTabsContent"] { border: none !important; }

/* ── hide default streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── radio horizontal pill style ── */
div[data-testid="stRadio"] > div {
    display: flex; flex-wrap: wrap; gap: 8px;
}
div[data-testid="stRadio"] label {
    background: #111c2d;
    border: 1px solid #1e2d42;
    border-radius: 20px;
    padding: 5px 14px;
    cursor: pointer;
    color: #7a9bb5;
    font-size: 13px;
}
div[data-testid="stRadio"] label:has(input:checked) {
    background: #1e3a5f;
    border-color: #2c5282;
    color: #60b4ff;
}
div[data-testid="stRadio"] input { display: none; }

/* ── dividers ── */
hr { border-color: #1e2d42 !important; }
</style>
""", unsafe_allow_html=True)


# ── data ──────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_df() -> pd.DataFrame:
    return query_profiles(limit=10_000)

@st.cache_data(ttl=300)
def load_stats() -> dict:
    return get_summary_stats()

@st.cache_data(ttl=300)
def cached_max_exp() -> int:
    return get_max_exp()


# ── path helpers ──────────────────────────────────────────────────────────────

def _is_mbb_company(co: str) -> bool:
    return bool(MBB_RE.search(co or ""))

def _firm_of_company(co: str) -> str:
    for firm, pat in [
        ("McKinsey", re.compile(r"mckinsey", re.I)),
        ("BCG",      re.compile(r"boston consulting|bcg\b", re.I)),
        ("Bain",     re.compile(r"bain & company|\bbain\b(?! capital)", re.I)),
    ]:
        if pat.search(co or ""):
            return firm
    return ""

def _fmt_year(val) -> str:
    if not val or str(val).strip().lower() in ("", "nan", "none"):
        return ""
    m = re.search(r"\d{4}", str(val))
    return m.group() if m else ""

def _clean_roles(company: str, title: str, all_titles_raw: str) -> list[str]:
    """Return distinct meaningful role titles — filters out company-name echoes."""
    co_norm = company.lower().strip()

    def is_noise(t: str) -> bool:
        t = t.strip()
        if not t:
            return True
        tl = t.lower()
        if tl == co_norm:
            return True
        # reject if it's just a minor variation (one contains the other)
        if co_norm in tl or tl in co_norm:
            return True
        return False

    candidates: list[str] = []
    if all_titles_raw and str(all_titles_raw).strip().lower() not in ("", "nan", "none"):
        for t in str(all_titles_raw).split(";"):
            t = t.strip()
            if t and not is_noise(t) and t not in candidates:
                candidates.append(t)

    if not candidates and title and not is_noise(title):
        candidates.append(title.strip())

    return candidates


# MBB seniority ladders by approximate tenure in years
_MBB_LADDER = [
    (0, 1,   "Business Analyst"),
    (1, 2.5, "Associate / Consultant"),
    (2.5, 4, "Engagement Manager"),
    (4, 6,   "Associate Principal"),
    (6, 9,   "Principal / Project Leader"),
    (9, 99,  "Partner / Director"),
]

def _infer_mbb_level(start: str, end: str) -> str:
    """Estimate MBB level from tenure duration when no title data is available."""
    try:
        s = int(start) if start else None
        e = int(end)   if end   else None
        if s and e:
            yrs = e - s
        elif s:
            yrs = 2026 - s      # assume still there or recently left
        else:
            return ""
        for lo, hi, label in _MBB_LADDER:
            if lo <= yrs < hi:
                return label
    except Exception:
        pass
    return ""


def get_full_path(row, max_exp: int) -> list[dict]:
    """ALL experience + education steps chronological (oldest → newest)."""
    raw = []
    for i in range(max_exp, 0, -1):
        co = row.get(f"exp_{i}_company")
        if not co:
            continue
        is_mbb_flag = row.get(f"exp_{i}_is_mbb") == 1
        is_mbb_name = _is_mbb_company(co)
        start      = _fmt_year(row.get(f"exp_{i}_start"))
        end        = _fmt_year(row.get(f"exp_{i}_end"))
        title      = str(row.get(f"exp_{i}_title") or "")
        all_titles = str(row.get(f"exp_{i}_all_titles") or "")
        roles      = _clean_roles(co, title, all_titles)
        raw.append({
            "type":    "work",
            "company": co,
            "roles":   roles,
            "is_mbb":  is_mbb_flag or is_mbb_name,
            "start":   start,
            "end":     end,
            "li_idx":  i,
        })

    # Add education nodes
    edu_fields = [
        ("undergrad_school", "undergrad_year", "undergrad_start_year", "undergrad", "Undergrad"),
        ("ms_school",        "ms_year",        "ms_start_year",        "ms",        "MS / MA"),
        ("mba_school",       "mba_year",       "mba_start_year",       "mba",       "MBA"),
        ("phd_school",       "phd_year",       "phd_start_year",       "phd",       "PhD"),
    ]
    for school_col, year_col, start_year_col, edu_type, label in edu_fields:
        school     = row.get(school_col)
        year       = _fmt_year(row.get(year_col))
        start_year = _fmt_year(row.get(start_year_col)) or year
        school_str = str(school).strip() if school and str(school).strip().lower() not in ("", "nan", "none") else ""
        # Skip entirely if no school name AND no year
        if not school_str and not year:
            continue
        raw.append({
            "type":     "education",
            "edu_type": edu_type,
            "company":  school_str or label,  # fall back to "Undergrad" / "MBA" label if no school name
            "roles":    [label],
            "is_mbb":   False,
            "start":    start_year,  # sort by start year so edu anchors correctly
            "end":      year,
            "li_idx":   0,
        })

    # Sort chronologically; undergrad always anchors at the beginning
    _EDU_DURATION = {"undergrad": 4, "mba": 2, "ms": 1.5, "phd": 5}

    def sort_key(s):
        if s.get("type") == "education" and s.get("edu_type") == "undergrad":
            return -1
        try:
            yr = int(s["start"]) if s["start"] else 0
            # When no start_year data, start==end (grad year); estimate real start
            if s.get("type") == "education" and s.get("start") == s.get("end"):
                dur = _EDU_DURATION.get(s.get("edu_type", ""), 2)
                yr = yr - dur
            return yr
        except (ValueError, TypeError):
            return 0

    raw.sort(key=sort_key)
    return raw


# ── industry label helper ─────────────────────────────────────────────────────

# Retail / consumer banking — shown in industry pill but NOT in Finance filter
_FIN_SERVICES_RE = re.compile(
    r"citigroup|\bciti\b|capital one|american express|\bamex\b|"
    r"fidelity investments|charles schwab|vanguard|wells fargo|"
    r"bank of america|\bhsbc\b|raymond james|edward jones|navy federal|credit union|"
    r"liberty mutual|massmutual|progressive insurance|transunion|"
    r"\bregions bank\b|m&t bank|comerica|citizens\b|aon\b|\bwtw\b|"
    r"insurance|reinsurance", re.I
)

# Energy & industrial — pill only, stays in "Other" destination
_ENERGY_RE = re.compile(
    r"\bshell\b|ge aerospace|ge vernova|lockheed martin|schneider electric|"
    r"\bhoneywell\b|nextera|engie\b|dte vantage|fervo|sunnova|\bbechtel\b|"
    r"\bspacex\b|globalfoundries|infineon|\baptiv\b|lucid motors|"
    r"hanwha|baseload power|anthro energy|carbon direct|lunar energy|"
    r"pattern energy|blue bird|oak ridge national|atmus|coorstek", re.I
)

# Legal — pill only, stays in "Other" destination
_LEGAL_RE = re.compile(
    r"debevoise|ropes & gray|ropes and gray|simpson thacher|wilmer|"
    r"wachtell|o'melveny|mcdermott will|epstein becker|"
    r"caplin.*drysdale|barker viggato|"
    r"district attorney|attorney.*office|\bllp\b|\blaw firm\b", re.I
)

_INDUSTRY_RULES = [
    ("MAANG",          "#0d1f3a", "#60a0ff", lambda co, ti: bool(MAANG_RE.search(co))),
    ("Tech",           "#0d220d", "#4caf50", lambda co, ti: bool(ENTERPRISE_TECH_RE.search(co))),
    ("Startup",        "#0a200a", "#a5d6a7", lambda co, ti: bool(STARTUP_RE.search(co))),
    ("IB / Finance",   "#1e2a00", "#c9a227", lambda co, ti: bool(IB_RE.search(co))),
    ("PE / VC",        "#1a1800", "#ffd54f", lambda co, ti: bool(PE_VC_RE.search(co))),
    ("Fin. Services",  "#1a1e10", "#a8c060", lambda co, ti: bool(_FIN_SERVICES_RE.search(co))),
    ("Energy",         "#0a1a0a", "#66bb6a", lambda co, ti: bool(_ENERGY_RE.search(co))),
    ("Legal",          "#0d0d1e", "#90caf9", lambda co, ti: bool(_LEGAL_RE.search(co))),
    ("Consulting",     "#2a1400", "#ff9800", lambda co, ti: bool(CONSULTING_RE.search(co))),
    ("MBB",            "#0d2a1a", "#00c853", lambda co, ti: bool(MBB_CURRENT_RE.search(co))),
    ("Healthcare",     "#1a0a2e", "#ce93d8", lambda co, ti: bool(HEALTHCARE_RE.search(co))),
    ("Consumer",       "#2a0a0a", "#ef9a9a", lambda co, ti: bool(CONSUMER_RE.search(co))),
    ("Govt / NGO",     "#0a1a2e", "#64b5f6", lambda co, ti: bool(GOVT_NONPROFIT_RE.search(co))),
    ("Academia",       "#12103a", "#9fa8da", lambda co, ti: bool(ACADEMIA_RE.search(co))),
    ("Founder",        "#2a2a00", "#fff176", lambda co, ti: bool(FOUNDER_TITLE_RE.search(ti))),
]

def _get_industry(co: str, ti: str) -> tuple[str, str, str]:
    """Returns (label, bg_color, text_color) for the current industry."""
    co, ti = co or "", ti or ""
    for label, bg, tc, fn in _INDUSTRY_RULES:
        if fn(co, ti):
            return label, bg, tc
    return "Other", "#111c2d", "#5a7a95"


_ROLE_RULES = [
    ("Founder",        "#2a2a00", "#fff176", lambda co, ti: bool(FOUNDER_TITLE_RE.search(ti))),
    ("Investor",       "#1a1800", "#ffd54f", lambda co, ti: bool(IB_RE.search(co)) or bool(PE_VC_RE.search(co)) or bool(INVESTING_TITLE_RE.search(ti))),
    ("Product",        "#0a200a", "#a5d6a7", lambda co, ti: bool(PM_TITLE_RE.search(ti))),
    ("Strategy & Ops", "#0d220d", "#4caf50", lambda co, ti: bool(STRATEGY_OPS_TITLE_RE.search(ti))),
    ("Consulting",     "#2a1400", "#ff9800", lambda co, ti: bool(CONSULTING_RE.search(co)) or bool(CONSULTING_TITLE_RE.search(ti))),
    ("Legal",          "#0d0d1e", "#90caf9", lambda co, ti: bool(_LEGAL_RE.search(co))),
]

def _get_role(co: str, ti: str) -> tuple[str, str, str] | None:
    """Returns (label, bg_color, text_color) for the current role, or None."""
    co, ti = co or "", ti or ""
    for label, bg, tc, fn in _ROLE_RULES:
        if fn(co, ti):
            return label, bg, tc
    return None


# ── row HTML ──────────────────────────────────────────────────────────────────

ARROW = '<span style="color:#253447;font-size:16px;margin:0 6px;align-self:center">→</span>'

def _step_chip(step: dict, is_dest: bool, firm: str) -> str:
    company = step["company"]
    roles   = step["roles"]        # list[str]
    start   = step["start"]
    end     = step["end"]
    is_mbb  = step["is_mbb"]
    is_edu  = step.get("type") == "education"

    short_co = (company[:22] + "…") if len(company) > 22 else company

    if is_edu:
        edu_type = step.get("edu_type", "")
        if edu_type == "mba":
            bg, border, tc, role_color = "#1e1040", "#7c4dff", "#b39ddb", "#7c4dff"
        elif edu_type == "phd":
            bg, border, tc, role_color = "#0d2a2a", "#00bcd4", "#80deea", "#00bcd4"
        elif edu_type == "ms":
            bg, border, tc, role_color = "#0d1f2a", "#29b6f6", "#81d4fa", "#29b6f6"
        else:  # undergrad
            bg, border, tc, role_color = "#1a1a2e", "#5c6bc0", "#9fa8da", "#5c6bc0"
    elif is_dest and not is_mbb:
        bg, border, tc = DEST_BG, DEST_COLOR, DEST_COLOR
        role_color = "#a06010"
    elif is_mbb:
        bg         = FIRM_BG.get(firm, "#1a2a3a")
        border     = FIRM_COLOR.get(firm, "#4f8ef7")
        tc         = FIRM_COLOR.get(firm, "#4f8ef7")
        role_color = "#5a8a6a" if firm == "BCG" else ("#3a7a9a" if firm == "McKinsey" else "#7a3a3a")
    else:
        bg, border, tc = "#141f2e", "#253447", "#8ba3be"
        role_color = "#4a6070"

    year_str = ""
    if is_edu:
        year_str = end or start or ""  # show graduation year for education chips
    elif start or end:
        year_str = f"{start}–{end}" if (start and end) else (start or end)

    # Roles: show data titles; for MBB with no titles, infer from tenure
    display_roles = list(roles)
    if is_mbb and not display_roles:
        inferred = _infer_mbb_level(start, end)
        if inferred:
            display_roles = [inferred]

    roles_html = ""
    for idx, r in enumerate(display_roles):
        short_r = (r[:28] + "…") if len(r) > 28 else r
        prefix  = "↳ " if idx > 0 else ""
        roles_html += (
            f'<div style="font-size:10px;color:{role_color};margin-top:2px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:170px">'
            f'{escape(prefix + short_r)}</div>'
        )

    year_html = (
        f'<div style="font-size:10px;color:#334455;margin-top:2px">{escape(year_str)}</div>'
        if year_str else ""
    )

    return f"""
<div style="display:flex;flex-direction:column;align-items:flex-start;min-width:100px;max-width:175px">
  <div style="background:{bg};border:1.5px solid {border};border-radius:8px;
              padding:5px 11px;color:{tc};font-size:12px;font-weight:600;
              white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:175px">
    {escape(short_co)}
  </div>
  {roles_html}
  {year_html}
</div>"""


def profile_row_html(row, max_exp: int, dest_co: str, highlight: bool = False) -> str:
    steps = get_full_path(row, max_exp)
    firm  = str(row.get("mbb_firms") or "").split(",")[0].strip()

    path_html = ARROW.join(
        _step_chip(
            s,
            is_dest=(dest_co and (
                s["company"] == dest_co or dest_co.lower() in s["company"].lower()
            )),
            firm=firm,
        )
        for s in steps
    )

    name = str(row.get("name") or row.get("profile_id") or "Unknown")
    parts = name.split()
    display = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]
    location = str(row.get("location") or "")

    cur_co = row.get("current_company") or ""
    cur_ti = row.get("current_title") or ""
    ind_label, ind_bg, ind_tc = _get_industry(cur_co, cur_ti)
    industry_pill = (
        f'<div style="margin-top:5px;display:inline-block;background:{ind_bg};'
        f'border:1px solid {ind_tc}33;border-radius:10px;padding:2px 8px;'
        f'font-size:10px;color:{ind_tc};font-weight:600">{escape(ind_label)}</div>'
    )
    role_result = _get_role(cur_co, cur_ti)
    role_pill = ""
    if role_result:
        rl, rb, rt = role_result
        role_pill = (
            f'<div style="margin-top:4px;display:inline-block;background:{rb};'
            f'border:1px solid {rt}33;border-radius:10px;padding:2px 8px;'
            f'font-size:10px;color:{rt};font-weight:600">{escape(rl)}</div>'
        )

    card_bg     = "#0d1f3a" if highlight else "#111c2d"
    card_border = "1.5px solid #3a7ab8" if highlight else "1px solid #1a2840"
    card_glow   = "box-shadow:0 0 10px #1a4a8044;" if highlight else ""

    return f"""
<div style="background:{card_bg};border:{card_border};border-radius:10px;
            padding:14px 18px;margin-bottom:8px;display:flex;align-items:flex-start;gap:18px;{card_glow}">
  <div style="min-width:110px;max-width:130px">
    <div style="font-weight:700;color:#d0dcea;font-size:13px">{escape(display)}</div>
    <div style="font-size:11px;color:#3a5060;margin-top:3px">{escape(location[:22]+"…" if len(location)>22 else location)}</div>
    {industry_pill}
    {role_pill}
  </div>
  <div style="display:flex;flex-wrap:wrap;align-items:flex-start;gap:4px;flex:1">
    {path_html}
  </div>
</div>"""


# ── archetype sections ────────────────────────────────────────────────────────

def render_archetype(label: str, subset: pd.DataFrame, dest_co: str, max_exp: int):
    if subset.empty:
        return
    count = len(subset)

    st.markdown(f"""
<div style="border-left:4px solid {DEST_COLOR};padding-left:14px;margin:28px 0 14px">
  <span style="font-size:20px;font-weight:700;color:#e8f0f8">MBB → {label}</span>
  <span style="float:right;background:#1a2a3a;border:1px solid #253447;
               border-radius:20px;padding:3px 12px;font-size:12px;color:#7a9bb5">
    {count:,} profiles
  </span>
</div>""", unsafe_allow_html=True)

    highlight_cards = label in ("MAANG", "Big Tech")
    for _, row in subset.iterrows():
        exit_co = row.get("exit_company") or dest_co
        st.markdown(profile_row_html(row, max_exp, exit_co, highlight=highlight_cards), unsafe_allow_html=True)


# ── main ──────────────────────────────────────────────────────────────────────

df      = load_df()
stats   = load_stats()
max_exp = cached_max_exp()

# mark MBB steps with name-matching fallback
for i in range(1, max_exp + 1):
    col = f"exp_{i}_is_mbb"
    name_col = f"exp_{i}_company"
    if col in df.columns and name_col in df.columns:
        df[col] = df[col].fillna(0).astype(int)
        df.loc[df[name_col].apply(lambda c: _is_mbb_company(str(c or ""))), col] = 1

# ── resolve post-MBB exit: use pre-computed columns, fall back to dynamic ──────
def _resolve_exit(r) -> tuple[str, str]:
    co = str(r.get("post_mbb_company") or "").strip()
    ti = str(r.get("post_mbb_title") or "").strip()
    if ti:
        parts = [t.strip() for t in ti.split(";") if t.strip()]
        ti = parts[-1] if parts else ti
    # If the stored post-MBB role is intern/candidate-like, treat as missing
    if not co or _INTERN_TITLE_RE.search(ti + " " + co):
        co, ti = _get_primary_exit(r, max_exp)
    return co, ti

_exits = df.apply(_resolve_exit, axis=1)
df["exit_company"]  = [e[0] for e in _exits]
df["exit_title"]    = [e[1] for e in _exits]
df["exit_category"] = df.apply(
    lambda r: _classify_exit(r["exit_company"], r["exit_title"]), axis=1
)

# ── header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:4px">
  <h1 style="font-size:28px;font-weight:800;color:#e8f0f8;margin:0">
    MBB Alumni — Career Path Archetypes
  </h1>
  <p style="color:#5a7a95;margin:4px 0 0;font-size:14px">
    Career journeys of McKinsey, BCG &amp; Bain alumni across
    """ + f"{stats['total_profiles']:,}" + """ profiles
  </p>
</div>""", unsafe_allow_html=True)

# ── destination filter (labels include counts) ────────────────────────────────
cat_counts = df["exit_category"].value_counts()

def _label(k):
    if k == "All":
        return f"All  ({len(df):,})"
    n = cat_counts.get(k, 0)
    return f"{k}  ({n:,})"

dest_keys    = list(DESTINATIONS.keys())
dest_labels  = [_label(k) for k in dest_keys]
label_to_key = dict(zip(dest_labels, dest_keys))

selected_label = st.radio(
    "DESTINATION", dest_labels, horizontal=True, label_visibility="collapsed"
)
selected = label_to_key[selected_label]

st.divider()

# ── metrics ───────────────────────────────────────────────────────────────────
has_full_path = df[[c for c in df.columns if c.endswith("_company")]].notna().sum(axis=1) >= 2

def _co(r): return r.get("current_company") or ""
def _ti(r): return r.get("current_title") or ""

# Section B — Degrees on record
n_mba  = df["mba_school"].notna().sum() if "mba_school" in df.columns else 0
n_ms   = df["ms_school"].notna().sum()  if "ms_school"  in df.columns else 0
n_phd  = df["phd_school"].notna().sum() if "phd_school" in df.columns else 0
n_jd   = df["jd_school"].notna().sum()  if "jd_school"  in df.columns else 0

st.markdown('<p style="color:#5a7a95;font-size:12px;margin:12px 0 4px;text-transform:uppercase;letter-spacing:.08em">Degrees on Record</p>', unsafe_allow_html=True)
d1, d2, d3, d4, d5 = st.columns(5)
d1.metric("Had MBA",    f"{n_mba:,}")
d2.metric("Had MS/MA",  f"{n_ms:,}")
d3.metric("Had PhD",    f"{n_phd:,}")
d4.metric("Had JD",     f"{n_jd:,}")
d5.metric("Total w/ Adv. Degree", f"{df[['mba_school','ms_school','phd_school','jd_school']].notna().any(axis=1).sum():,}")

st.divider()

# ── legend ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px;font-size:12px">
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#00854A;vertical-align:middle;margin-right:5px"></span>MCK / BCG / Bain</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#1e3d6b;vertical-align:middle;margin-right:5px"></span>Google</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#7a3200;vertical-align:middle;margin-right:5px"></span>Amazon</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#1e3a5f;vertical-align:middle;margin-right:5px"></span>Meta</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#1a3a1a;vertical-align:middle;margin-right:5px"></span>Microsoft</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#1a1a2e;vertical-align:middle;margin-right:5px"></span>Undergrad</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#1e1040;vertical-align:middle;margin-right:5px"></span>MBA</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#0d1f2a;vertical-align:middle;margin-right:5px"></span>MS / MA</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#0d2a2a;vertical-align:middle;margin-right:5px"></span>PhD</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#5a3a00;vertical-align:middle;margin-right:5px"></span>PE / VC</span>
  <span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;
    background:#141f2e;vertical-align:middle;margin-right:5px"></span>Corporate / Other</span>
</div>""", unsafe_allow_html=True)

# ── helper: filter df by archetype ────────────────────────────────────────────
def _filter_archetype(df, key):
    if key == "All":
        return df
    return df[df["exit_category"] == key]

# ── filter + render archetypes ────────────────────────────────────────────────
matcher = DESTINATIONS[selected]

ALL_KEYS = EXIT_CATEGORY_LABELS + ["Other"]

def _render_archetype_preview(label, key):
    subset = _filter_archetype(df, key)
    preview = subset.head(5)
    render_archetype(label, preview, key, max_exp)
    remaining = len(subset) - len(preview)
    if remaining > 0:
        st.markdown(
            f'<div style="text-align:center;color:#4a6070;font-size:12px;'
            f'padding:8px;border:1px dashed #1e2d42;border-radius:8px;margin-bottom:8px">'
            f'+ {remaining:,} more — select <b>{label}</b> above to see all</div>',
            unsafe_allow_html=True,
        )

if selected == "All":
    for key in ALL_KEYS:
        _render_archetype_preview(key, key)
else:
    subset = _filter_archetype(df, selected)

    # ── company sub-filter ────────────────────────────────────────────────────
    companies = sorted(c for c in subset["exit_company"].dropna().unique() if c)
    if companies:
        selected_cos = st.multiselect(
            "Filter by company",
            options=companies,
            placeholder="All companies in this bucket",
            label_visibility="collapsed",
        )
        if selected_cos:
            subset = subset[subset["exit_company"].isin(selected_cos)]

    render_archetype(selected, subset, selected, max_exp)
