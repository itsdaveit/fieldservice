"""
Service Report Review Pipeline

Mehrstufige Pipeline zur automatischen Korrektur von Service-Report-Beschreibungen
vor der Überführung in Lieferscheine.

Jeder Step bekommt Zugriff auf die Ergebnisse vorheriger Steps, sodass spätere
Steps (z.B. LLM) auf bereits korrigierte Texte zugreifen können.
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    step_name: str        # z.B. "bullet_formatting"
    field: str            # z.B. "work[0].description"
    original_value: str
    suggested_value: str  # None wenn nur Warnung
    change_type: str      # "auto_fix", "suggestion", "warning", "error"
    message: str          # Menschenlesbarer Text

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class ReviewStep(ABC):
    """Base class for pipeline steps."""

    name: str = "unnamed_step"

    @abstractmethod
    def execute(self, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        """Run this step. Return list of ReviewResults."""
        ...


class ReviewPipeline:
    """Runs a sequence of ReviewSteps against a Service Report document."""

    def __init__(self, doc):
        self.doc = doc
        self.results: list[ReviewResult] = []
        self.steps: list[ReviewStep] = []

    def add_step(self, step: ReviewStep):
        self.steps.append(step)
        return self

    def run(self) -> list[ReviewResult]:
        for step in self.steps:
            step_results = step.execute(self.doc, self.results)
            self.results.extend(step_results)
        return self.results

    def apply_auto_fixes(self):
        """Apply all auto_fix results directly to the document."""
        applied = []
        for result in self.results:
            if result.change_type != "auto_fix" or not result.suggested_value:
                continue

            # Parse field reference like "work[2].description"
            m = re.match(r'work\[(\d+)\]\.description', result.field)
            if m:
                idx = int(m.group(1))
                if idx < len(self.doc.work):
                    self.doc.work[idx].description = result.suggested_value
                    applied.append(result)

        return applied

    def get_fixes(self) -> list[ReviewResult]:
        """Return only results that have suggested changes."""
        return [r for r in self.results if r.suggested_value and r.change_type in ("auto_fix", "suggestion")]

    def results_as_json(self) -> str:
        return json.dumps([r.to_dict() for r in self.results], ensure_ascii=False)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

QUILL_BULLET_TEMPLATE = (
    '<li data-list="bullet">'
    '<span class="ql-ui" contenteditable="false"></span>'
    '{text}'
    '</li>'
)


def extract_paragraphs(html: str) -> list[str]:
    """Extract text content from <p> tags in Quill HTML.

    Returns list of paragraph texts (may contain inline HTML like <br>).
    Skips empty paragraphs.
    """
    # Remove ql-editor wrapper
    html = re.sub(r'<div class="ql-editor[^"]*">', '', html)
    html = re.sub(r'</div>\s*$', '', html)

    paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)

    result = []
    for p in paragraphs:
        # Strip trailing <br> tags
        text = re.sub(r'<br\s*/?>$', '', p).strip()
        if text:
            result.append(text)
    return result


def is_bullet_prefix(text: str) -> bool:
    """Check if text starts with a dash used as bullet point (not arrow ->)."""
    stripped = text.lstrip()
    if not stripped.startswith('-'):
        return False
    # Check it's not an arrow (-> or -&gt;)
    after_dash = stripped[1:]
    if after_dash.startswith('>') or after_dash.startswith('&gt;'):
        return False
    return True


def strip_bullet_prefix(text: str) -> str:
    """Remove leading dash and optional whitespace from bullet text."""
    stripped = text.lstrip()
    if stripped.startswith('-'):
        stripped = stripped[1:].lstrip()
    return stripped


def paragraphs_to_bullet_html(paragraphs: list[str]) -> str:
    """Convert list of paragraph texts to Quill bullet-list HTML."""
    items = []
    for text in paragraphs:
        items.append(QUILL_BULLET_TEMPLATE.format(text=text))
    return '<ol>' + ''.join(items) + '</ol>'


# ---------------------------------------------------------------------------
# Step 1: Bullet Formatting
# ---------------------------------------------------------------------------

class BulletFormattingStep(ReviewStep):
    """Convert dash-prefixed paragraphs to Quill bullet lists.

    Input:  <p>-Scanner installiert</p><p>-System getestet</p>
    Output: <ol><li data-list="bullet">...Scanner installiert</li>...</ol>
    """

    name = "bullet_formatting"

    def execute(self, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        results = []

        for i, work in enumerate(doc.work):
            desc = work.description
            if not desc:
                continue

            # Skip if already formatted as bullet list
            if '<li data-list="bullet">' in desc:
                continue

            paragraphs = extract_paragraphs(desc)
            if not paragraphs:
                continue

            # Check if any paragraph starts with a dash bullet
            has_bullets = any(is_bullet_prefix(p) for p in paragraphs)
            if not has_bullets:
                continue

            # Need at least one paragraph to convert
            # Strip dash prefix from all paragraphs (mixed with/without dash)
            cleaned = []
            for p in paragraphs:
                if is_bullet_prefix(p):
                    cleaned.append(strip_bullet_prefix(p))
                else:
                    cleaned.append(p)

            new_html = paragraphs_to_bullet_html(cleaned)

            if new_html != desc:
                results.append(ReviewResult(
                    step_name=self.name,
                    field=f"work[{i}].description",
                    original_value=desc,
                    suggested_value=new_html,
                    change_type="auto_fix",
                    message=f"Position {i+1}: {len(cleaned)} Aufzählungspunkte formatiert",
                ))

        return results


# ---------------------------------------------------------------------------
# Step 2: Capitalization
# ---------------------------------------------------------------------------

class CapitalizationStep(ReviewStep):
    """Capitalize first letter of bullet items after dash removal.

    Only acts on descriptions that were already converted to bullet lists
    (either by BulletFormattingStep or pre-existing).
    """

    name = "capitalization"

    def execute(self, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        results = []

        for i, work in enumerate(doc.work):
            # Get the current or already-corrected description
            field_key = f"work[{i}].description"
            desc = self._get_current_value(field_key, work.description, previous_results)
            if not desc:
                continue

            # Only process bullet lists
            if '<li data-list="bullet">' not in desc:
                continue

            new_desc = self._capitalize_bullets(desc)
            if new_desc != desc:
                results.append(ReviewResult(
                    step_name=self.name,
                    field=field_key,
                    original_value=desc,
                    suggested_value=new_desc,
                    change_type="auto_fix",
                    message=f"Position {i+1}: Großschreibung korrigiert",
                ))

        return results

    def _get_current_value(self, field_key: str, original: str,
                           previous_results: list[ReviewResult]) -> str:
        """Get the latest value for a field, considering previous step results."""
        for result in reversed(previous_results):
            if result.field == field_key and result.suggested_value:
                return result.suggested_value
        return original

    def _capitalize_bullets(self, html: str) -> str:
        """Capitalize first letter after each bullet span."""
        def capitalize_match(m):
            prefix = m.group(1)
            first_char = m.group(2)
            return prefix + first_char.upper()

        # Match the closing </span> followed by the first letter
        return re.sub(
            r'(contenteditable="false"></span>)([a-zäöü])',
            capitalize_match,
            html
        )


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------

def build_default_pipeline(doc) -> ReviewPipeline:
    """Build the standard review pipeline with all active steps."""
    pipeline = ReviewPipeline(doc)
    pipeline.add_step(BulletFormattingStep())
    pipeline.add_step(CapitalizationStep())
    return pipeline
