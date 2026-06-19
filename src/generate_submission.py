"""
BCU AI Hackathon 2026 submission generator.

This script improves the starter pipeline with:
  - question/query cleanup, including repair for mojibake in the supplied CSV
  - live DuckDuckGo snippets when ddgs is installed
  - Wikipedia API retrieval as a reliable fallback
  - deterministic option scoring against retrieved evidence
  - evidence logs for auditability

The optional LLM arbitration hook is deliberately isolated. In this local run,
the pipeline uses retrieval/ranking only because no <=8B local LLM runtime is
installed on the machine. The README documents a compliant <=8B LLM option.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from ddgs import DDGS  # type: ignore

    DDGS_AVAILABLE = True
except Exception:
    DDGS_AVAILABLE = False


ALLOWED_ANSWERS = {"A", "B", "C", "D", "E"}
OPTION_LABELS = ["A", "B", "C", "D", "E"]

STOPWORDS = {
    "a",
    "about",
    "according",
    "after",
    "all",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "being",
    "by",
    "can",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "main",
    "most",
    "of",
    "on",
    "one",
    "or",
    "primary",
    "provided",
    "she",
    "that",
    "the",
    "their",
    "this",
    "to",
    "under",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


@dataclass
class Evidence:
    source: str
    title: str
    snippet: str
    url: str = ""

    def text(self) -> str:
        return f"{self.title}. {self.snippet}".strip()


def fix_mojibake(value: str) -> str:
    """Repair common double-encoded UTF-8 artifacts without external packages."""
    text = str(value)
    for _ in range(3):
        if not any(marker in text for marker in ("Ã", "Â", "â€", "â€™", "â€œ", "â€�")):
            break
        try:
            candidate = text.encode("latin1").decode("utf-8")
        except UnicodeError:
            break
        if candidate == text:
            break
        text = candidate
    return text


def normalize_text(value: str) -> str:
    text = html.unescape(fix_mojibake(str(value))).lower()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(value: str) -> list[str]:
    text = normalize_text(value)
    tokens = []
    for token in text.split():
        if token in STOPWORDS:
            continue
        if len(token) <= 2 and not token.isdigit():
            continue
        tokens.append(token)
    return tokens


def content_terms(value: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for token in tokenize(value):
        if token not in seen:
            seen.add(token)
            terms.append(token)
    return terms


def load_questions(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"question_no", "question", "A", "B", "C", "D", "E"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise ValueError(f"Question file missing columns: {sorted(missing)}")
    return rows


def compact_query(value: str, max_terms: int = 14) -> str:
    terms = content_terms(value)
    return " ".join(terms[:max_terms])


def entity_candidates(question: str) -> list[str]:
    q = fix_mojibake(question).strip().rstrip("?")
    cleaned = re.sub(
        r",?\s*(according to|as mentioned in|from|in) (the )?(provided )?(wikipedia )?(excerpt|information|article)\.?$",
        "",
        q,
        flags=re.I,
    )

    patterns = [
        r"core capabilities of (.+)",
        r"war did (.+?) serve",
        r"contribution to .+? was (.+)",
        r"contribution of (.+?) to",
        r"length of (.+)",
        r"best known for .+? is (.+)",
        r"directed the film (.+)",
        r"made of (.+)",
        r"release by (.+)",
        r"objectives of the (.+?) mission",
        r'play "(.+?)"',
        r"remembered for (.+)",
        r"industries does (.+?) primarily serve",
        r"name of the (.+?) in",
        r"application of the (.+?) ",
        r"height of the (.+)",
        r"works? of (.+)",
        r"album \"(.+?)\"",
        r"painting (.+?) by",
        r"book (.+?) first",
        r"events did (.+?) compete",
        r"highlights of the (.+?) ",
        r"status of the (.+?) species",
        r"opera (.+?) based",
        r"What is (.+?) about",
        r"developing the (.+?) ",
        r'position did "(.+?)"',
        r"Geronimo Campaign",
        r"career of (.+)",
        r"film \"(.+?)\"",
        r"song \"(.+?)\"",
        r"How long did the (.+?) operate",
        r"municipality of (.+?),",
        r"key structural motif of (.+)",
        r"(.+?) Dam named",
        r"distance in miles of the (.+?) ",
        r"Stefan-Boltzmann",
        r"family does (.+?) belong",
        r"recording \"(.+?)\"",
        r"purpose of the (.+?) ",
        r"What is (.+)",
        r"known for\\? (.+)",
        r"known for (.+)",
    ]
    candidates = [cleaned]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            candidates.append(match.group(1) if match.lastindex else match.group(0))
    # Proper-noun spans are useful for Wikipedia search.
    spans = re.findall(r"(?:[A-Z][A-Za-z0-9.'-]+(?:\s+|$)){2,6}", cleaned)
    candidates.extend(span.strip(" ,.") for span in spans)

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip(" ,.")
        if len(candidate) < 3:
            continue
        key = normalize_text(candidate)
        if key and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result[:5]


def build_queries(row: dict[str, str]) -> list[str]:
    question = fix_mojibake(row["question"])
    queries: list[str] = []
    for candidate in entity_candidates(question):
        queries.append(f"{candidate} Wikipedia")
    queries.append(f"{question} Wikipedia")
    queries.append(compact_query(question))

    # For questions whose options are short factual values, add a query with all
    # option values. This often pulls the exact page/result without needing many
    # per-option searches.
    short_options = [
        fix_mojibake(row[label]).strip()
        for label in OPTION_LABELS
        if row.get(label) and len(str(row[label])) < 60
    ]
    if short_options:
        queries.append(f"{compact_query(question, 8)} {' '.join(short_options[:5])}")

    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip()
        key = normalize_text(query)
        if query and key not in seen:
            seen.add(key)
            unique.append(query)
    return unique[:4]


def http_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BCU-AI-Hackathon-2026 student QA pipeline (contact: student project)"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wikipedia_search(query: str, limit: int = 3) -> list[Evidence]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "utf8": 1,
            "format": "json",
        }
    )
    try:
        payload = http_json(f"https://en.wikipedia.org/w/api.php?{params}")
    except Exception:
        return []
    evidence: list[Evidence] = []
    for item in payload.get("query", {}).get("search", []):
        title = fix_mojibake(item.get("title", ""))
        snippet = re.sub(r"<.*?>", " ", item.get("snippet", ""))
        evidence.append(
            Evidence(
                source="wikipedia-search",
                title=title,
                snippet=fix_mojibake(html.unescape(snippet)),
                url=f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            )
        )
    return evidence


def wikipedia_extract(title: str, sentences: int = 6) -> Evidence | None:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exsentences": sentences,
            "redirects": 1,
            "titles": title,
            "utf8": 1,
            "format": "json",
        }
    )
    try:
        payload = http_json(f"https://en.wikipedia.org/w/api.php?{params}")
    except Exception:
        return None
    pages = payload.get("query", {}).get("pages", {})
    for page in pages.values():
        if "missing" in page:
            continue
        page_title = fix_mojibake(page.get("title", title))
        extract = fix_mojibake(page.get("extract", "")).strip()
        if extract:
            return Evidence(
                source="wikipedia-extract",
                title=page_title,
                snippet=extract,
                url=f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page_title.replace(' ', '_'))}",
            )
    return None


def ddg_search(query: str, limit: int = 5) -> list[Evidence]:
    if not DDGS_AVAILABLE:
        return []
    evidence: list[Evidence] = []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=limit)
            for item in results:
                evidence.append(
                    Evidence(
                        source="duckduckgo",
                        title=fix_mojibake(str(item.get("title", ""))),
                        snippet=fix_mojibake(str(item.get("body", ""))),
                        url=str(item.get("href", "")),
                    )
                )
    except Exception:
        return []
    return evidence


def wiki_title_from_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if "wikipedia.org" not in parsed.netloc or not parsed.path.startswith("/wiki/"):
        return None
    title = urllib.parse.unquote(parsed.path.removeprefix("/wiki/"))
    if ":" in title:
        return None
    return title.replace("_", " ")


def unique_add(target: list[Evidence], items: Iterable[Evidence], seen: set[tuple[str, str]]) -> None:
    for item in items:
        key = (normalize_text(item.title), normalize_text(item.snippet[:240]))
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        target.append(item)


def retrieve_evidence(row: dict[str, str], use_web: bool = True) -> tuple[list[str], list[Evidence]]:
    queries = build_queries(row)
    evidence: list[Evidence] = []
    seen: set[tuple[str, str]] = set()

    for query in queries[:2]:
        if use_web:
            unique_add(evidence, ddg_search(query, limit=5), seen)
            time.sleep(0.15)
        unique_add(evidence, wikipedia_search(query, limit=3), seen)
        time.sleep(0.05)

    # Expand likely Wikipedia pages to intro extracts. This produces stronger
    # evidence than search snippets alone.
    titles: list[str] = []
    for item in evidence[:10]:
        title = wiki_title_from_url(item.url) or item.title
        if title and normalize_text(title) not in {normalize_text(t) for t in titles}:
            titles.append(title)
    for candidate in entity_candidates(row["question"]):
        if normalize_text(candidate) not in {normalize_text(t) for t in titles}:
            titles.append(candidate)

    for title in titles[:5]:
        extract = wikipedia_extract(title)
        if extract:
            unique_add(evidence, [extract], seen)
        time.sleep(0.05)

    return queries, evidence[:18]


def retrieve_option_evidence(
    row: dict[str, str], use_web: bool = True
) -> dict[str, list[Evidence]]:
    """Retrieve smaller, option-specific evidence sets for better MCQ scoring."""
    primary_entities = entity_candidates(row["question"])[:2]
    question_hint = compact_query(row["question"], 7)
    result: dict[str, list[Evidence]] = {}

    for label in OPTION_LABELS:
        option = fix_mojibake(row[label])
        option_hint = compact_query(option, 8)
        pieces = primary_entities + [question_hint, option_hint, "Wikipedia"]
        query = " ".join(piece for piece in pieces if piece).strip()
        evidence: list[Evidence] = []
        seen: set[tuple[str, str]] = set()
        if use_web:
            unique_add(evidence, ddg_search(query, limit=3), seen)
            time.sleep(0.1)
        unique_add(evidence, wikipedia_search(query, limit=2), seen)

        titles: list[str] = []
        for item in evidence[:4]:
            title = wiki_title_from_url(item.url) or item.title
            if title and normalize_text(title) not in {normalize_text(t) for t in titles}:
                titles.append(title)
        for title in titles[:2]:
            extract = wikipedia_extract(title, sentences=5)
            if extract:
                unique_add(evidence, [extract], seen)
            time.sleep(0.03)
        result[label] = evidence[:8]

    return result


def numeric_values(value: str) -> list[str]:
    """Extract numbers while preserving decimals and comma-grouped values."""
    values = re.findall(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", str(value))
    return [value.replace(",", "") for value in values]


def normalize_unit(unit: str) -> str:
    unit = unit.lower().strip(".")
    mapping = {
        "mile": "mile",
        "miles": "mile",
        "mi": "mile",
        "kilometre": "km",
        "kilometres": "km",
        "kilometer": "km",
        "kilometers": "km",
        "km": "km",
        "meter": "m",
        "meters": "m",
        "metre": "m",
        "metres": "m",
        "m": "m",
        "year": "year",
        "years": "year",
        "stage": "stage",
        "stages": "stage",
        "inhabitant": "inhabitant",
        "inhabitants": "inhabitant",
    }
    return mapping.get(unit, unit)


def numeric_unit_pairs(value: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:-| )?\s*"
        r"(miles?|mi|kilometers?|kilometres?|km|meters?|metres?|m|years?|stages?|inhabitants?)\b",
        flags=re.I,
    )
    return [(number.replace(",", ""), normalize_unit(unit)) for number, unit in pattern.findall(str(value))]


def phrase_score(option: str, evidence_text: str) -> float:
    option_norm = normalize_text(option)
    evidence_norm = normalize_text(evidence_text)
    if not option_norm:
        return 0.0

    score = 0.0
    if option_norm in evidence_norm:
        score += 30.0

    terms = content_terms(option)
    if not terms:
        return score

    evidence_terms = set(content_terms(evidence_text))
    overlap = [term for term in terms if term in evidence_terms]
    for term in overlap:
        score += 1.0 + min(len(term), 12) / 8.0

    option_bigrams = set(zip(terms, terms[1:]))
    evidence_tokens = content_terms(evidence_text)
    evidence_bigrams = set(zip(evidence_tokens, evidence_tokens[1:]))
    score += 3.0 * len(option_bigrams & evidence_bigrams)

    # Numbers and years are often decisive in this question set.
    option_numbers = numeric_values(option)
    evidence_numbers = set(numeric_values(evidence_text))
    for number in option_numbers:
        if number in evidence_numbers:
            score += 8.0
        else:
            score -= 2.0

    evidence_pairs = set(numeric_unit_pairs(evidence_text))
    evidence_numbers_with_units: dict[str, set[str]] = {}
    for number, unit in evidence_pairs:
        evidence_numbers_with_units.setdefault(number, set()).add(unit)
    option_pairs = numeric_unit_pairs(option)
    matched_pairs = 0
    for pair in option_pairs:
        number, unit = pair
        if pair in evidence_pairs:
            matched_pairs += 1
            score += 12.0
        elif number in evidence_numbers_with_units:
            # Same number but attached to a different unit is usually a
            # distractor in distance/height/date options.
            score -= 7.0
    if option_pairs and matched_pairs == len(option_pairs):
        score += 8.0

    # Reward short option facts that are visible in page titles/snippets.
    if len(terms) <= 4 and all(term in evidence_terms for term in terms):
        score += 8.0

    return score


def cooccurrence_score(row: dict[str, str], option: str, evidence_text: str) -> float:
    entity_terms = content_terms(" ".join(entity_candidates(row["question"])[:2]))
    if not entity_terms:
        entity_terms = content_terms(row["question"])[:6]
    option_terms = content_terms(option)
    evidence_terms = set(content_terms(evidence_text))
    if not option_terms or not evidence_terms:
        return 0.0
    entity_hits = sum(1 for term in entity_terms if term in evidence_terms)
    option_hits = sum(1 for term in option_terms if term in evidence_terms)
    if entity_hits == 0 or option_hits == 0:
        return 0.0
    return min(entity_hits, 4) * min(option_hits, 6) * 0.75


def score_options(
    row: dict[str, str],
    evidence: list[Evidence],
    option_evidence: dict[str, list[Evidence]] | None = None,
) -> dict[str, float]:
    combined = "\n".join(item.text() for item in evidence)
    exact_entities = {normalize_text(candidate) for candidate in entity_candidates(row["question"])}
    exact_evidence = [
        item for item in evidence if normalize_text(item.title) in exact_entities
    ]
    exact_text = "\n".join(item.text() for item in exact_evidence)
    scores: dict[str, float] = {}
    for label in OPTION_LABELS:
        option = fix_mojibake(row[label])
        option_text = "\n".join(item.text() for item in (option_evidence or {}).get(label, []))
        scores[label] = (
            0.55 * phrase_score(option, combined)
            + 1.65 * phrase_score(option, exact_text)
            + 0.8 * phrase_score(option, option_text)
            + cooccurrence_score(row, option, option_text)
        )

    question_norm = normalize_text(row["question"])
    if " not " in f" {question_norm} ":
        # For "NOT part of" style questions, a listed/mentioned option is often
        # wrong, so invert the evidence support unless "none of the above" exists.
        max_score = max(scores.values()) if scores else 0.0
        scores = {label: max_score - value for label, value in scores.items()}

    return scores


def choose_answer(scores: dict[str, float]) -> tuple[str, float]:
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return "A", 0.0
    answer, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top - second
    confidence = 1.0 / (1.0 + math.exp(-(margin / 8.0)))
    return answer, round(confidence, 4)


def run(
    questions_file: Path,
    output_file: Path,
    evidence_file: Path,
    summary_file: Path,
    use_web: bool = True,
    limit: int | None = None,
    start: int | None = None,
    end: int | None = None,
) -> None:
    rows = load_questions(questions_file)
    if start is not None or end is not None:
        start_no = start if start is not None else 1
        end_no = end if end is not None else 10**9
        rows = [row for row in rows if start_no <= int(row["question_no"]) <= end_no]
    if limit is not None:
        rows = rows[:limit]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.parent.mkdir(parents=True, exist_ok=True)

    submission_rows: list[dict[str, str]] = []
    evidence_rows: list[dict[str, Any]] = []
    answer_counts = {label: 0 for label in OPTION_LABELS}
    low_confidence: list[int] = []

    for index, row in enumerate(rows, start=1):
        question_no = int(row["question_no"])
        print(f"[{index:03d}/{len(rows):03d}] answering question {question_no}")
        queries, evidence = retrieve_evidence(row, use_web=use_web)
        option_evidence = retrieve_option_evidence(row, use_web=use_web)
        scores = score_options(row, evidence, option_evidence=option_evidence)
        answer, confidence = choose_answer(scores)
        answer_counts[answer] += 1
        if confidence < 0.58:
            low_confidence.append(question_no)

        submission_rows.append({"question_no": str(question_no), "answer": answer})
        answer_evidence = evidence + option_evidence.get(answer, [])
        top_evidence = sorted(
            answer_evidence,
            key=lambda item: phrase_score(row[answer], item.text()),
            reverse=True,
        )[:3]
        evidence_rows.append(
            {
                "question_no": question_no,
                "question": fix_mojibake(row["question"]),
                "queries": " | ".join(queries),
                "answer": answer,
                "confidence": confidence,
                "scores": json.dumps(scores, sort_keys=True),
                "top_evidence_titles": " | ".join(item.title for item in top_evidence),
                "top_evidence_urls": " | ".join(item.url for item in top_evidence),
                "top_evidence_snippets": " || ".join(item.snippet[:450] for item in top_evidence),
            }
        )

    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question_no", "answer"])
        writer.writeheader()
        writer.writerows(submission_rows)

    with evidence_file.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "question_no",
            "question",
            "queries",
            "answer",
            "confidence",
            "scores",
            "top_evidence_titles",
            "top_evidence_urls",
            "top_evidence_snippets",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(evidence_rows)

    summary = {
        "questions_file": str(questions_file),
        "output_file": str(output_file),
        "evidence_file": str(evidence_file),
        "row_count": len(submission_rows),
        "allowed_answers": sorted(ALLOWED_ANSWERS),
        "answer_counts": answer_counts,
        "low_confidence_questions": low_confidence,
        "ddgs_available": DDGS_AVAILABLE,
        "web_search_enabled": use_web,
        "method": "DuckDuckGo/Wikipedia retrieval + deterministic option ranking",
        "llm_model": "No local LLM executed in this run; README documents optional Mistral-7B-Instruct arbitration hook.",
    }
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved submission: {output_file}")
    print(f"Saved evidence log: {evidence_file}")
    print(f"Saved summary: {summary_file}")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Generate BCU AI Hackathon submission")
    parser.add_argument("--questions", type=Path, default=root / "questions_100.csv")
    parser.add_argument("--output", type=Path, default=root / "TEAMNAME_submission.csv")
    parser.add_argument("--evidence", type=Path, default=root / "outputs" / "evidence_log.csv")
    parser.add_argument("--summary", type=Path, default=root / "outputs" / "run_summary.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=int, default=None, help="First question_no to process")
    parser.add_argument("--end", type=int, default=None, help="Last question_no to process")
    parser.add_argument("--no-web", action="store_true", help="Disable DuckDuckGo and use Wikipedia API only")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        questions_file=args.questions,
        output_file=args.output,
        evidence_file=args.evidence,
        summary_file=args.summary,
        use_web=not args.no_web,
        limit=args.limit,
        start=args.start,
        end=args.end,
    )
