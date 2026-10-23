"""Relevance: a cheap title filter first, then Claude scores what's left against the CV."""
import os
import re
from typing import Literal

from pydantic import BaseModel, Field

from .common import Job, log

ROLE_PATTERNS = {
    "DevOps / Cloud": r"devops|devsecops|cloud\s*(engineer|ops|operations)|site reliability|\bsre\b|platform engineer|infrastructure engineer|kubernetes|aws engineer",
    "Analyst": r"analyst|אנליסט|analytics|\bbi\b|business intelligence|data analyst|מנתח",
    "Project Manager": r"project manager|program manager|\bpmo\b|delivery manager|implementation manager|מנהל[ת]? פרויקט",
    "Product Manager": r"product manager|product owner|\bapm\b|associate product|מנהל[ת]? מוצר",
}
EXCLUDE = re.compile(
    r"\b(senior|sr\.?|lead|leader|head|director|principal|staff|vp|chief|architect|manager of|group manager)\b|"
    r"\bnoc\b|\bsoc\b|security operations|network operations|cyber|security analyst|threat|\bmdr\b|monitoring analyst|"
    r"intern\b|student|סטודנט|בכיר",
    re.I,
)
# At gaming companies and early-stage startups, roles outside the target titles are also
# worth seeing as a way in ("foot in the door").
FOOT_IN_DOOR = (
    r"operations|\bops\b|liveops|live ops|customer success|support|implementation|onboarding|"
    r"solutions? engineer|integration|qa\b|quality assurance|\bit\b|helpdesk|system admin|"
    r"user acquisition|\bua\b|monetization|game economy|payments|billing|revenue|revops|"
    r"account manager|community|coordinator|associate|specialist|junior|ג'וניור|תפעול|תמיכה"
)
FOOT_IN_DOOR_CATEGORY = "דריסת רגל"


def prefilter(job: Job):
    """Returns the matched category, or None if the job is clearly irrelevant."""
    title = job.title or ""
    if EXCLUDE.search(title):
        return None
    for cat, pat in ROLE_PATTERNS.items():
        if re.search(pat, title, re.I):
            return cat
    if job.extra.get("broad") and re.search(FOOT_IN_DOOR, title, re.I):
        return FOOT_IN_DOOR_CATEGORY
    return None


class Verdict(BaseModel):
    score: int = Field(description="0-100: how good a fit this job is for the candidate")
    level_fit: Literal["fits", "too_senior", "too_junior", "unclear"]
    reason_he: str = Field(description="One or two short sentences in Hebrew explaining the score")


SYSTEM = """You screen job postings for one specific candidate and score how well each fits.

Candidate profile and CV summary:
{profile}

Scoring guide:
- 80-100: role type is a target, seniority is junior/entry or "1-2 years", most required skills match.
- 60-79: good role type, some gaps or asks for ~2-3 years.
- 30-59: related but weak fit (big skill gaps, or unclear seniority).
- 0-29: wrong role type, clearly senior (4+ years), shift-based NOC/SOC monitoring, or outside Israel without remote option.
If the job is marked "foot in the door", the candidate is open to a role outside their target titles
at a gaming company or early-stage startup as a way in: score it on whether they could realistically
get hired with their background (ops, payments, incident handling, CRM, SQL/Python, DevOps basics),
not on whether the title is a target.
Write reason_he in natural Hebrew, concrete (name the matching or missing skills)."""


class Scorer:
    def __init__(self, profile_text: str, model: str | None = None):
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
        self.client = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic()
        else:
            log.warning("ANTHROPIC_API_KEY not set: using keyword scoring only")
        self.system = SYSTEM.format(profile=profile_text)

    def score(self, job: Job):
        if not self.client:
            return self._keyword_score(job)
        import anthropic
        try:
            resp = self.client.messages.parse(
                model=self.model,
                max_tokens=2000,
                output_config={"effort": "low"},
                system=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": (
                    f"Title: {job.title}\nCompany: {job.company}\nLocation: {job.location}\n"
                    f"{'Foot in the door: yes (' + job.extra.get('broad') + ')' if job.extra.get('broad') else ''}\n\n"
                    f"Description:\n{(job.description or '(no description available, judge from title)')[:8000]}"
                )}],
                output_format=Verdict,
            )
        except anthropic.RateLimitError:
            log.warning("Rate limited while scoring; falling back to keywords for %s", job.title)
            return self._keyword_score(job)
        except anthropic.APIStatusError as e:
            log.warning("Claude API error %s for %s", e.status_code, job.title)
            return self._keyword_score(job)
        except anthropic.APIConnectionError:
            return self._keyword_score(job)
        if resp.stop_reason == "refusal" or not resp.parsed_output:
            return self._keyword_score(job)
        v = resp.parsed_output
        job.score = max(0, min(100, v.score))
        if v.level_fit == "too_senior":
            job.score = min(job.score, 40)
        job.reason = v.reason_he

    SKILLS = ["linux", "docker", "kubernetes", "k8s", "aws", "eks", "terraform", "ci/cd", "github actions",
              "python", "sql", "jenkins", "monitoring", "grafana", "prometheus", "sap", "agile", "jira",
              "excel", "tableau", "power bi", "payments", "fintech", "erp", "crm"]

    def _keyword_score(self, job: Job):
        text = f"{job.title}\n{job.description}".lower()
        hits = [s for s in self.SKILLS if s in text]
        # "at least 2 years", "3+ years", "2-3 years", "שנתיים"
        years = [int(y) for y in re.findall(r"(\d)\s*(?:\+|-\s*\d)?\s*(?:years|yrs|שנות|שנים)", text)]
        if "שנתיים" in text:
            years.append(2)
        score = 45 + 4 * min(len(hits), 6)
        if years:
            need = max(years)
            score -= 35 if need >= 3 else 20 if need == 2 else 0
        if re.search(r"junior|entry|graduate|ג'וניור|ללא ניסיון", text):
            score += 10
        job.score = max(0, min(85, score))  # keywords alone can't justify a "perfect" match
        parts = []
        if hits:
            parts.append("מילות מפתח תואמות: " + ", ".join(hits[:6]))
        if years and max(years) >= 2:
            parts.append(f"דורשת {max(years)}+ שנות ניסיון")
        job.reason = ". ".join(parts) if parts else "התאמה לפי שם התפקיד בלבד"
        job.reason += " (דירוג לפי מילות מפתח)"
