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
# Step 3: LLM Text Correction
# ---------------------------------------------------------------------------

DEFAULT_AI_SYSTEM_PROMPT = """\
Du bist ein Qualitätsprüfer für Service-Reports eines IT-Dienstleisters (itsdave GmbH).

Techniker erstellen Service Reports nach erledigter Arbeit. Diese werden in Lieferscheine überführt, die an Kunden gehen. Du prüfst und korrigierst die Texte, bevor sie den Kunden erreichen.

## Deine Aufgaben

### 1. Titel korrigieren
- Korrekte Groß-/Kleinschreibung (deutsch)
- Rechtschreibung
- Beispiel: "SIP Trunk Easybell anpassung" → "SIP-Trunk Easybell Anpassung"
- Beispiel: "Mobilteil einrichtung 3CX" → "Mobilteileinrichtung 3CX"

### 2. Beschreibungstexte korrigieren
- Grammatik und Rechtschreibung korrigieren (deutsch, außer englische Fachbegriffe)
- Text kundengerecht formulieren (professionell, klar, technischen Inhalt beibehalten)
- Abkürzungen beibehalten wenn branchenüblich (VPN, AD, DNS, DHCP, RDP, etc.)
- KEINE inhaltlichen Änderungen oder Ergänzungen
- Das Format ist <p>• Text</p> — behalte dieses Format exakt bei
- Jeder Aufzählungspunkt bleibt ein eigener <p>• ...</p> Absatz

### 3. Service-Typ bewerten
Erkenne ob die Arbeit tatsächlich Remote oder Vor-Ort stattfand.
Starke Vor-Ort-Indikatoren: "vor Ort", "VO", "Mitnahme", "mitgenommen", "aufgebaut", "ausgeliefert", "abgeholt", Verkabelung, Umzug, Einbau, "Serverraum"
Starke Remote-Indikatoren: "TV Support" (TeamViewer), "Fernwartung", "TRMM", "Telefonat", reine Konfigurationsarbeiten

### 4. Hardware-Hinweise
Prüfe ob in den Arbeitspositionen Hardware erwähnt wird, die physisch bewegt wurde (aufgebaut, ausgetauscht, installiert, geliefert, mitgebracht, angeschlossen). Vergleiche mit der Liste der erfassten Artikel. Wenn Hardware in den Beschreibungen erwähnt wird, aber NICHT in den Artikeln erfasst ist, gib einen Hinweis.
Relevante Hardware: PCs, Laptops, Notebooks, Server, Switches, Router, Firewalls, Access Points, DECT-Basen, Mobilteile/Telefone, Monitore, Drucker, USV, NAS, Festplatten, SSDs, Kameras, Kabel, USB-Sticks.
NUR physisch bewegte Hardware zählt — nicht wenn sie nur konfiguriert oder repariert wird.

## Wichtig
- Behalte den technischen Inhalt exakt bei
- Ändere keine Fakten, Zeitangaben oder Kundennamen
- Wenn ein Text bereits korrekt ist, nimm ihn NICHT in die Korrekturen auf

## Antwortformat
Antworte NUR mit einem JSON-Objekt in exakt diesem Format (keine Markdown-Codeblocks):
{
  "titel_korrektur": {
    "original": "Originaler Titel",
    "korrigiert": "Korrigierter Titel",
    "aenderungen": ["rechtschreibung"]
  },
  "korrekturen": [
    {
      "idx": 1,
      "korrigierter_text": "<p>• Korrigierter Text</p><p>• Zweiter Punkt</p>",
      "aenderungen": ["rechtschreibung", "grammatik"]
    }
  ],
  "service_typ_bewertung": {
    "aktueller_typ": "Remote Service",
    "empfohlener_typ": "On-Site Service",
    "konfidenz": "sicher",
    "begruendung": "Kurze Begründung"
  },
  "hinweise": [
    {
      "typ": "fehlende_hardware",
      "position_idx": 1,
      "beschreibung": "SNOM M900 DECT-Basen und Mobilteile wurden aufgebaut/angeschlossen, aber kein Material auf dem Service Report erfasst.",
      "erkannte_hardware": ["SNOM M900 DECT-Basen", "Mobilteile"]
    }
  ]
}
Regeln:
- "korrekturen" enthält NUR Positionen die Korrekturen brauchen (leeres Array wenn alles korrekt)
- "titel_korrektur.aenderungen" ist leer wenn der Titel korrekt ist
- "idx" ist 1-basiert (Position 1 = idx 1)
- "korrigierter_text" muss im <p>• Text</p> HTML-Format sein
- "hinweise" enthält Hinweise auf mögliche Probleme (leeres Array wenn keine)
- "hinweise[].typ" kann sein: "fehlende_hardware", "sonstiger_hinweis"
- "hinweise[].position_idx" ist der 1-basierte Index der betroffenen Position (0 wenn global)\
"""

LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["titel_korrektur", "korrekturen", "service_typ_bewertung", "hinweise"],
    "additionalProperties": False,
    "properties": {
        "titel_korrektur": {
            "type": "object",
            "required": ["original", "korrigiert", "aenderungen"],
            "additionalProperties": False,
            "properties": {
                "original": {"type": "string"},
                "korrigiert": {"type": "string"},
                "aenderungen": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste der Änderungen, leer wenn keine nötig"
                }
            }
        },
        "korrekturen": {
            "type": "array",
            "description": "Nur Positionen die Korrekturen brauchen. Leer wenn alles korrekt.",
            "items": {
                "type": "object",
                "required": ["idx", "korrigierter_text", "aenderungen"],
                "additionalProperties": False,
                "properties": {
                    "idx": {
                        "type": "integer",
                        "description": "1-basierter Index der Arbeitsposition"
                    },
                    "korrigierter_text": {
                        "type": "string",
                        "description": "Korrigierter HTML-Text im <p>• Text</p> Format"
                    },
                    "aenderungen": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Art der Änderungen: rechtschreibung, grammatik, grossschreibung, formulierung"
                    }
                }
            }
        },
        "service_typ_bewertung": {
            "type": "object",
            "required": ["aktueller_typ", "empfohlener_typ", "konfidenz", "begruendung"],
            "additionalProperties": False,
            "properties": {
                "aktueller_typ": {
                    "type": "string",
                    "enum": ["Remote Service", "On-Site Service", "Application Development"]
                },
                "empfohlener_typ": {
                    "type": "string",
                    "enum": ["Remote Service", "On-Site Service", "Application Development"]
                },
                "konfidenz": {
                    "type": "string",
                    "enum": ["sicher", "wahrscheinlich", "unsicher"]
                },
                "begruendung": {"type": "string"}
            }
        },
        "hinweise": {
            "type": "array",
            "description": "Hinweise auf mögliche Probleme (fehlende Hardware etc.). Leer wenn keine.",
            "items": {
                "type": "object",
                "required": ["typ", "position_idx", "beschreibung"],
                "additionalProperties": False,
                "properties": {
                    "typ": {
                        "type": "string",
                        "enum": ["fehlende_hardware", "sonstiger_hinweis"],
                        "description": "Art des Hinweises"
                    },
                    "position_idx": {
                        "type": "integer",
                        "description": "1-basierter Index der betroffenen Position, 0 wenn global"
                    },
                    "beschreibung": {
                        "type": "string",
                        "description": "Menschenlesbarer Hinweistext"
                    },
                    "erkannte_hardware": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste der erkannten Hardware-Bezeichnungen"
                    }
                }
            }
        }
    }
}


def _strip_html(html: str) -> str:
    """Strip HTML tags for plain-text display in prompts."""
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _capitalize_labels(labels: list) -> list:
    """Capitalize correction type labels for display."""
    if not isinstance(labels, list):
        return labels
    mapping = {
        "rechtschreibung": "Rechtschreibung",
        "grammatik": "Grammatik",
        "grossschreibung": "Großschreibung",
        "formulierung": "Formulierung",
        "formatierung": "Formatierung",
        "textkorrektur": "Textkorrektur",
        "korrigiert": "Korrigiert",
    }
    return [mapping.get(l, l.capitalize() if isinstance(l, str) else l) for l in labels]


class LLMTextCorrectionStep(ReviewStep):
    """Call Claude API to correct spelling, grammar, and phrasing."""

    name = "llm_text_correction"

    def __init__(self, api_key: str, model: str, system_prompt: str):
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-20250514"
        self.system_prompt = system_prompt or DEFAULT_AI_SYSTEM_PROMPT

    def execute(self, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        import anthropic

        # Build user prompt with all work descriptions
        positions = []
        for i, work in enumerate(doc.work):
            desc = self._get_current_value(f"work[{i}].description", work.description, previous_results)
            if desc:
                plain = _strip_html(desc)
                positions.append(f"**Position {i+1}** (Service-Typ: {getattr(work, 'service_type', 'unbekannt')}):\n{plain}")

        if not positions:
            return []

        # Build items list
        items_text = "(keine Artikel erfasst)"
        if hasattr(doc, 'items') and doc.items:
            items_lines = []
            for it in doc.items:
                items_lines.append(f"- {getattr(it, 'item_code', '?')}: {getattr(it, 'item_name', '?')} (Menge: {getattr(it, 'qty', '?')})")
            items_text = "\n".join(items_lines)

        user_prompt = (
            f"## Service Report\n\n"
            f"**Titel:** {getattr(doc, 'titel', '') or ''}\n"
            f"**Service-Typ (gewählt):** {getattr(doc, 'report_type', '') or ''}\n\n"
            f"### Arbeitspositionen:\n\n" +
            "\n\n".join(positions) +
            f"\n\n### Erfasste Artikel:\n{items_text}"
        )

        # Call Claude API with tool use to enforce JSON schema
        client = anthropic.Anthropic(api_key=self.api_key)

        tool_definition = {
            "name": "submit_review",
            "description": "Reiche das Ergebnis der Textprüfung ein.",
            "input_schema": LLM_RESPONSE_SCHEMA,
        }

        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool_definition],
            tool_choice={"type": "tool", "name": "submit_review"},
        )

        # Extract structured data from tool use response
        data = None
        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_review":
                data = block.input
                break

        if not data or not isinstance(data, dict):
            return []

        return self._parse_response(data, doc, previous_results)

    def _parse_response(self, data: dict, doc, previous_results: list[ReviewResult]) -> list[ReviewResult]:
        """Parse LLM response flexibly — handles various JSON structures."""
        results = []

        # --- Title correction ---
        # Handles: titel_korrektur.korrigiert, titel.korrigiert
        titel_korr = data.get("titel_korrektur") or data.get("titel") or {}
        if isinstance(titel_korr, dict):
            original = titel_korr.get("original", "")
            korrigiert = titel_korr.get("korrigiert", "")
            needs_fix = titel_korr.get("aenderungen") or titel_korr.get("benoetigt_korrektur")
            if needs_fix and korrigiert and korrigiert != original:
                aenderungen = _capitalize_labels(titel_korr.get("aenderungen", []))
                msg = "Titel: " + (", ".join(aenderungen) if isinstance(aenderungen, list) and aenderungen else "Korrigiert")
                results.append(ReviewResult(
                    step_name=self.name, field="titel",
                    original_value=original, suggested_value=korrigiert,
                    change_type="suggestion", message=msg,
                ))

        # --- Work description corrections ---
        # Handles: korrekturen[].korrigierter_text or positionen[].beschreibung.korrigiert
        corrections = data.get("korrekturen") or data.get("positionen") or []
        if not isinstance(corrections, list):
            corrections = []

        for korr in corrections:
            if not isinstance(korr, dict):
                continue

            # Get position index (1-based in various field names)
            idx = (korr.get("idx") or korr.get("position") or 0) - 1
            if idx < 0 or idx >= len(doc.work):
                continue

            # Get suggested text — various structures
            suggested = korr.get("korrigierter_text", "")
            if not suggested:
                beschreibung = korr.get("beschreibung")
                if isinstance(beschreibung, dict):
                    suggested = beschreibung.get("korrigiert", "")

            if not suggested:
                continue

            field_key = f"work[{idx}].description"
            current = self._get_current_value(field_key, doc.work[idx].description, previous_results)

            if suggested != current:
                aenderungen = korr.get("aenderungen", [])
                if not aenderungen and isinstance(korr.get("beschreibung"), dict):
                    if korr["beschreibung"].get("benoetigt_korrektur"):
                        aenderungen = ["textkorrektur"]
                msg_parts = _capitalize_labels(aenderungen if isinstance(aenderungen, list) and aenderungen else ["Korrigiert"])
                results.append(ReviewResult(
                    step_name=self.name, field=field_key,
                    original_value=current, suggested_value=suggested,
                    change_type="suggestion",
                    message=f"Position {idx+1}: " + ", ".join(msg_parts),
                ))

            # Service type per position — link to work[idx].service_type
            svc = korr.get("service_typ")
            if isinstance(svc, dict) and svc.get("benoetigt_aenderung"):
                results.append(ReviewResult(
                    step_name=self.name,
                    field=f"work[{idx}].service_type",
                    original_value=svc.get("original", ""),
                    suggested_value=svc.get("empfohlen", ""),
                    change_type="suggestion",
                    message=f"Service-Typ: {svc.get('begruendung', '')}",
                ))

        # --- Global service type warning (fallback) ---
        typ_bew = data.get("service_typ_bewertung") or {}
        if (isinstance(typ_bew, dict) and typ_bew.get("empfohlener_typ") and
                typ_bew.get("empfohlener_typ") != typ_bew.get("aktueller_typ") and
                typ_bew.get("konfidenz") in ("sicher", "wahrscheinlich")):
            # Only add if no per-position service type results exist
            has_per_pos = any(r.field.endswith('.service_type') for r in results)
            if not has_per_pos:
                results.append(ReviewResult(
                    step_name=self.name, field="report_type",
                    original_value=typ_bew.get("aktueller_typ", ""),
                    suggested_value=typ_bew.get("empfohlener_typ", ""),
                    change_type="suggestion",
                    message=f"Service-Typ: {typ_bew.get('begruendung', '')}",
                ))

        # --- Hinweise (fehlende Hardware etc.) ---
        for hinweis in (data.get("hinweise") or []):
            if not isinstance(hinweis, dict):
                continue
            typ = hinweis.get("typ", "sonstiger_hinweis")
            pos_idx = hinweis.get("position_idx", 0)
            beschreibung = hinweis.get("beschreibung", "")
            hardware = hinweis.get("erkannte_hardware", [])

            if typ == "fehlende_hardware" and hardware:
                hw_list = ", ".join(hardware)
                message = f"Möglicherweise fehlendes Material: {hw_list}"
            else:
                message = beschreibung

            field = f"work[{pos_idx - 1}].hint" if pos_idx > 0 else "hint"
            results.append(ReviewResult(
                step_name=self.name,
                field=field,
                original_value=beschreibung,
                suggested_value=None,
                change_type="hint",
                message=message,
            ))

        return results

    def _get_current_value(self, field_key: str, original: str,
                           previous_results: list[ReviewResult]) -> str:
        for result in reversed(previous_results):
            if result.field == field_key and result.suggested_value:
                return result.suggested_value
        return original


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------

def build_default_pipeline(doc) -> ReviewPipeline:
    """Build the standard review pipeline with all active steps."""
    pipeline = ReviewPipeline(doc)
    pipeline.add_step(BulletFormattingStep())
    pipeline.add_step(CapitalizationStep())
    return pipeline
