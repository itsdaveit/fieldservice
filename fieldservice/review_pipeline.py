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

BULLET_CHAR = '\u2022'  # •


def extract_paragraphs(html: str) -> list[str]:
    """Extract raw content from <p> tags in Quill HTML.

    Returns list of paragraph contents (may contain inline HTML).
    Preserves empty paragraphs as empty strings for structure detection.
    """
    # Remove ql-editor wrapper
    html = re.sub(r'<div class="ql-editor[^"]*">', '', html)
    html = re.sub(r'</div>\s*$', '', html)

    paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)
    return paragraphs


def is_empty_paragraph(text: str) -> bool:
    """Check if paragraph is empty (just <br> or whitespace)."""
    cleaned = re.sub(r'<br\s*/?>', '', text).strip()
    return not cleaned


def clean_paragraph_text(text: str) -> str:
    """Clean a paragraph: strip trailing <br>, leading/trailing whitespace, &nbsp;."""
    text = re.sub(r'<br\s*/?>$', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.strip()
    return text


def is_dash_bullet(text: str) -> bool:
    """Check if cleaned text starts with a dash used as bullet (not arrow ->)."""
    if not text.startswith('-'):
        return False
    after_dash = text[1:]
    if after_dash.startswith('>') or after_dash.startswith('&gt;'):
        return False
    return True


def strip_dash(text: str) -> str:
    """Remove leading dash and optional whitespace."""
    if text.startswith('-'):
        return text[1:].lstrip()
    return text


def is_indented_sub_item(raw_text: str) -> bool:
    """Check if raw paragraph text is an indented sub-item (starts with spaces/nbsp + dash)."""
    cleaned = raw_text.replace('&nbsp;', ' ')
    # Must have at least 2 leading spaces before the dash
    stripped = cleaned.lstrip()
    leading_spaces = len(cleaned) - len(stripped)
    return leading_spaces >= 2 and is_dash_bullet(stripped)


def format_as_bullet_list(items: list[dict]) -> str:
    """Convert structured items to simple <p> tags with bullet character.

    Uses plain <p>• Text</p> format which renders consistently
    in Quill editor, print preview, and PDF — no list indentation issues.
    """
    parts = []
    for item in items:
        text = item['text']
        if not text:
            continue
        parts.append(f'<p>{BULLET_CHAR} {text}</p>')

    if not parts:
        return ''
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Step 1: Bullet Formatting
# ---------------------------------------------------------------------------

class BulletFormattingStep(ReviewStep):
    """Convert dash-prefixed paragraphs to uniform Quill bullet lists.

    Handles:
    - Simple: <p>-Text</p> → bullet item
    - With space: <p> - Text</p> → bullet item
    - Headings: <p>Heading</p> followed by <p>-item</p> → heading as bold bullet
    - Sub-items: <p> &nbsp; - sub item</p> → indented text with dash replaced
    - Empty paragraphs between sections are removed
    """

    name = "bullet_formatting"

    def execute(self, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        results = []

        for i, work in enumerate(doc.work):
            desc = work.description
            if not desc:
                continue

            # Check if this is an existing Quill bullet list that needs conversion
            has_quill_bullets = '<li data-list="bullet">' in desc

            if has_quill_bullets:
                # Convert existing Quill bullets to uniform <p>• format
                new_html = self._convert_quill_bullets(desc)
                if new_html and new_html != desc:
                    bullet_count = new_html.count(BULLET_CHAR)
                    results.append(ReviewResult(
                        step_name=self.name,
                        field=f"work[{i}].description",
                        original_value=desc,
                        suggested_value=new_html,
                        change_type="auto_fix",
                        message=f"Position {i+1}: {bullet_count} Aufzählungspunkte vereinheitlicht",
                    ))
                continue

            raw_paragraphs = extract_paragraphs(desc)
            if not raw_paragraphs:
                continue

            # Check if any paragraph has a dash bullet pattern
            has_any_bullet = False
            for raw_p in raw_paragraphs:
                cleaned = clean_paragraph_text(raw_p)
                if is_dash_bullet(cleaned):
                    has_any_bullet = True
                    break
                # Also check for " - " pattern (space-dash-space)
                stripped_raw = raw_p.replace('&nbsp;', ' ').strip()
                if is_dash_bullet(stripped_raw.lstrip()):
                    has_any_bullet = True
                    break

            if not has_any_bullet:
                continue

            # Parse into structured items
            items = self._parse_structured(raw_paragraphs)
            if not items:
                continue

            new_html = format_as_bullet_list(items)
            if not new_html or new_html == desc:
                continue

            bullet_count = len([it for it in items if it['text']])
            results.append(ReviewResult(
                step_name=self.name,
                field=f"work[{i}].description",
                original_value=desc,
                suggested_value=new_html,
                change_type="auto_fix",
                message=f"Position {i+1}: {bullet_count} Aufzählungspunkte formatiert",
            ))

        return results

    def _parse_structured(self, raw_paragraphs: list[str]) -> list[dict]:
        """Parse paragraphs into structured items with type detection.

        Recognizes:
        - Empty paragraphs (skipped)
        - Dash-prefixed items → bullet
        - Indented dash items → sub_bullet (text prefixed with "  ")
        - Non-dash paragraphs before bullets → heading (bold)
        - Non-dash paragraphs after bullets → regular bullet
        """
        items = []
        non_empty = []

        # First pass: collect non-empty paragraphs with their types
        for raw_p in raw_paragraphs:
            if is_empty_paragraph(raw_p):
                continue

            cleaned = clean_paragraph_text(raw_p)
            if not cleaned:
                continue

            if is_indented_sub_item(raw_p):
                # Indented sub-item: strip all leading whitespace and dash, no extra indent
                text = raw_p.replace('&nbsp;', ' ').strip()
                text = strip_dash(text)
                non_empty.append({'text': text, 'type': 'sub_bullet', 'raw': raw_p})
            elif is_dash_bullet(cleaned):
                text = strip_dash(cleaned)
                non_empty.append({'text': text, 'type': 'bullet', 'raw': raw_p})
            else:
                non_empty.append({'text': cleaned, 'type': 'plain', 'raw': raw_p})

        if not non_empty:
            return []

        # Second pass: determine if plain items are headings or regular bullets
        # A "plain" item followed by bullet items is a heading
        result = []
        for idx, item in enumerate(non_empty):
            if item['type'] == 'plain':
                # Look ahead: is the next non-plain item a bullet?
                next_items = non_empty[idx + 1:idx + 3]
                has_following_bullet = any(n['type'] in ('bullet', 'sub_bullet') for n in next_items)

                if has_following_bullet:
                    # This is a heading — make it bold
                    result.append({'text': '<strong>' + item['text'] + '</strong>', 'type': 'heading'})
                else:
                    # Regular item, just make it a bullet
                    result.append({'text': item['text'], 'type': 'bullet'})
            else:
                result.append(item)

        return result

    def _convert_quill_bullets(self, html: str) -> str:
        """Convert existing Quill <ul>/<ol> bullet lists to <p>• format."""
        # Extract text from each <li data-list="bullet">
        items = re.findall(
            r'<li data-list="bullet"><span[^>]*></span>\s*(.*?)\s*</li>',
            html, re.DOTALL
        )
        if not items:
            return None

        parts = []
        for text in items:
            text = text.strip()
            if text:
                parts.append(f'<p>{BULLET_CHAR} {text}</p>')

        return ''.join(parts) if parts else None


# ---------------------------------------------------------------------------
# Step 2: Capitalization
# ---------------------------------------------------------------------------

class CapitalizationStep(ReviewStep):
    """Capitalize first letter of bullet items.

    Works with the <p>• text</p> format.
    """

    name = "capitalization"

    def execute(self, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        results = []

        for i, work in enumerate(doc.work):
            field_key = f"work[{i}].description"
            desc = self._get_current_value(field_key, work.description, previous_results)
            if not desc:
                continue

            # Only process descriptions with bullet character
            if BULLET_CHAR not in desc:
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
        for result in reversed(previous_results):
            if result.field == field_key and result.suggested_value:
                return result.suggested_value
        return original

    def _capitalize_bullets(self, html: str) -> str:
        """Capitalize first letter after bullet character (skip bold/tags)."""
        def capitalize_match(m):
            return m.group(1) + m.group(2).upper()

        # Match "• " followed by a lowercase letter (not a tag like <strong>)
        return re.sub(
            rf'({re.escape(BULLET_CHAR)} )([a-zäöü])',
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
