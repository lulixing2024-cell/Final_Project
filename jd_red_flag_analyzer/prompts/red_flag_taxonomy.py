"""The Red Flag Taxonomy — Phase 3.

Eight categories split into:

  EXTERNAL-DRIVEN (rely on company/industry/role news + reviews):
    1. company_distress       — recent layoffs, restructuring, financial trouble
    2. culture_reputation     — public reviews/news of toxic culture, harassment
    3. legal_ethical_flags    — lawsuits, regulatory actions, scandals
    4. industry_role_headwinds — sector/role-level decline or disruption pressure

  JD-INTERNAL, PRESENCE-BASED (only triggered by explicit problematic phrases —
                                never by absence of "expected" content):
    5. overwork_glorification — language romanticizing overwork as virtue
    6. scope_dumping          — catchall phrases suggesting role = dumping ground
    7. hollow_promises        — empty growth/comp/career superlatives
    8. buzzword_urgency       — empty marketing words + urgency pressure tactics

Each definition includes bilingual (English + Chinese) example phrases so the
analyzer prompt grounds equally well in both languages.

The prompt template imports these definitions so the LLM and the code agree
on what each category means. Tests and UI also import from here.
"""

from dataclasses import dataclass

from core.schemas import RedFlagCategory


@dataclass(frozen=True)
class CategoryDefinition:
    category: RedFlagCategory
    display_name: str
    green_criteria: str
    yellow_criteria: str
    red_criteria: str
    examples_red: list[str]
    is_external_driven: bool  # routing hint for the analyzer prompt


TAXONOMY: list[CategoryDefinition] = [
    # =========================================================
    # EXTERNAL-DRIVEN
    # =========================================================
    CategoryDefinition(
        category=RedFlagCategory.COMPANY_DISTRESS,
        display_name="Company Distress",
        green_criteria=(
            "External research surfaces no concerning news. Company appears "
            "operationally and financially stable."
        ),
        yellow_criteria=(
            "Minor signals: one round of small layoffs, an executive departure, "
            "or a modest stock decline. Not yet structural."
        ),
        red_criteria=(
            "Significant recent layoffs, formal restructuring, financial "
            "distress, sustained mass leadership turnover, or acquisition/"
            "spin-off creating uncertainty."
        ),
        examples_red=[
            "20% workforce reduction",
            "filed for bankruptcy protection",
            "CEO and CFO resigned within weeks",
            "delisted from exchange",
        ],
        is_external_driven=True,
    ),
    CategoryDefinition(
        category=RedFlagCategory.CULTURE_REPUTATION,
        display_name="Culture Reputation",
        green_criteria=(
            "External reviews and news are consistently positive or neutral. "
            "No pattern of culture complaints."
        ),
        yellow_criteria=(
            "Mixed reviews, or specific complaints in some teams without a "
            "broader pattern. Common in any large company."
        ),
        red_criteria=(
            "Multiple independent sources describe toxic culture, harassment, "
            "996-style overwork, retaliation, or mass attrition for "
            "culture-related reasons."
        ),
        examples_red=[
            "widespread reports of burnout",
            "harassment lawsuit settled",
            "high attrition tied to management",
            "公开报道存在 996 文化",
        ],
        is_external_driven=True,
    ),
    CategoryDefinition(
        category=RedFlagCategory.LEGAL_ETHICAL_FLAGS,
        display_name="Legal & Ethical Flags",
        green_criteria=(
            "No material recent legal or ethical issues affecting employees "
            "or this function."
        ),
        yellow_criteria=(
            "Routine regulatory matters, settled minor disputes, or industry-"
            "typical compliance issues."
        ),
        red_criteria=(
            "Active major lawsuits, regulatory sanctions, public ethics "
            "scandals, or pattern of wage/labor violations."
        ),
        examples_red=[
            "wage theft class action",
            "SEC investigation announced",
            "regulatory fine for labor violations",
            "ethics scandal involving executives",
        ],
        is_external_driven=True,
    ),
    CategoryDefinition(
        category=RedFlagCategory.INDUSTRY_ROLE_HEADWINDS,
        display_name="Industry & Role Headwinds",
        green_criteria=(
            "Industry is stable or growing; this role/function is in demand."
        ),
        yellow_criteria=(
            "Industry under pressure (regulation, macro slowdown) but this "
            "role/function not directly threatened."
        ),
        red_criteria=(
            "Industry in significant decline, OR this specific role/function "
            "facing direct disruption (e.g., AI replacement, regulatory ban, "
            "mass offshoring) such that mid-term career risk is elevated."
        ),
        examples_red=[
            "sector-wide layoffs across multiple firms",
            "AI replacing this role function",
            "regulation expected to eliminate the role",
            "行业整体下行",
        ],
        is_external_driven=True,
    ),

    # =========================================================
    # JD-INTERNAL, PRESENCE-BASED
    # NOTE: All four require explicit problematic phrases in the JD.
    #       ABSENCE of typical content NEVER triggers a non-GREEN finding.
    # =========================================================
    CategoryDefinition(
        category=RedFlagCategory.OVERWORK_GLORIFICATION,
        display_name="Overwork Glorification",
        green_criteria=(
            "No language romanticizing overwork. Candidate-trait descriptors "
            "alone (self-driven / 自驱 / passionate / eager to learn) do NOT "
            "count — those are personal qualities, not company expectations."
        ),
        yellow_criteria=(
            "Tempo language suggesting an intense pace without explicit "
            "overwork glorification (e.g., 'fast-paced', 'high-energy')."
        ),
        red_criteria=(
            "JD contains explicit COMPANY-SIDE framing that overwork is a "
            "virtue or family-like commitment is expected."
        ),
        examples_red=[
            "we are a family",
            "work hard play hard",
            "always-on culture",
            "willing to go above and beyond",
            "we live and breathe our work",
            "我们是一个大家庭",
            "拼搏文化",
            "狼性文化",
            "能接受 996",
        ],
        is_external_driven=False,
    ),
    CategoryDefinition(
        category=RedFlagCategory.SCOPE_DUMPING,
        display_name="Scope Dumping Signals",
        green_criteria=(
            "Responsibilities are bounded and listed concretely, regardless "
            "of count. Absence of a long bullet list is NOT a red flag."
        ),
        yellow_criteria=(
            "Mild scope ambiguity — generic verbs (own, drive, lead) with no "
            "object, or 'and more' suffixes."
        ),
        red_criteria=(
            "Explicit catchall phrasing that signals the role is a dumping "
            "ground: anything required, build from nothing, do everything."
        ),
        examples_red=[
            "wear many hats",
            "other duties as assigned",
            "do whatever it takes",
            "jack of all trades",
            "build from scratch where needed",
            "适应公司发展需要承担其他工作",
            "其他相关工作",
            "一人多岗",
        ],
        is_external_driven=False,
    ),
    CategoryDefinition(
        category=RedFlagCategory.HOLLOW_PROMISES,
        display_name="Hollow Promises",
        green_criteria=(
            "No empty superlative promises. Specific growth/comp language is "
            "fine; lack of any such language is also fine — silence is NOT a "
            "red flag in this category."
        ),
        yellow_criteria=(
            "Vague growth language without substance ('great learning "
            "opportunity', 'be part of something big')."
        ),
        red_criteria=(
            "JD makes specific superlative promises that ring hollow — "
            "unlimited X, make millions, change the world — without any "
            "concrete structure backing them up."
        ),
        examples_red=[
            "limitless growth potential",
            "make millions in your first year",
            "be your own boss",
            "unprecedented opportunity",
            "rocketship trajectory",
            "广阔的发展空间",
            "实现财富自由",
            "改变世界的机会",
        ],
        is_external_driven=False,
    ),
    CategoryDefinition(
        category=RedFlagCategory.BUZZWORD_URGENCY,
        display_name="Buzzword & Urgency Density",
        green_criteria=(
            "Industry-standard terminology only (data-driven, user growth, "
            "A/B testing, 技术驱动业务, 用户增长). No urgency markers. "
            "Industry terms are NOT buzzwords."
        ),
        yellow_criteria=(
            "A few empty marketing buzzwords OR urgency markers, but not both."
        ),
        red_criteria=(
            "Multiple EMPTY buzzwords (rockstar, ninja, disrupt, paradigm "
            "shift, synergy, 赋能, 抓手) combined with explicit urgency markers "
            "(URGENT, hiring immediately, 急聘)."
        ),
        examples_red=[
            "URGENT — hiring immediately",
            "rockstar ninja needed",
            "disrupt the paradigm with synergy",
            "急聘",
            "立即到岗",
        ],
        is_external_driven=False,
    ),
]


def lookup(category: RedFlagCategory) -> CategoryDefinition:
    for cd in TAXONOMY:
        if cd.category == category:
            return cd
    raise KeyError(category)


# Verify at import time that every enum value has a definition
_categories_defined = {cd.category for cd in TAXONOMY}
_categories_enum = set(RedFlagCategory)
assert _categories_defined == _categories_enum, (
    f"TAXONOMY is incomplete. Missing: {_categories_enum - _categories_defined}, "
    f"Extra: {_categories_defined - _categories_enum}"
)
