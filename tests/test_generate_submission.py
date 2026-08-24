from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import generate_submission as pipeline  # noqa: E402


class PipelineTests(unittest.TestCase):
    def test_committed_submission_is_complete(self) -> None:
        with (ROOT / "Anthropic_submission.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 100)
        self.assertEqual([int(row["question_no"]) for row in rows], list(range(1, 101)))
        self.assertTrue(all(row["answer"] in pipeline.ALLOWED_ANSWERS for row in rows))

        final_answers = {int(row["question_no"]): row["answer"] for row in rows}
        reviewed = pipeline.load_reviewed_answers(
            ROOT / "outputs" / "recheck_flags_v2.csv"
        )
        self.assertTrue(
            all(final_answers[question_no] == answer for question_no, answer in reviewed.items())
        )

    def test_load_questions_rejects_missing_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.csv"
            path.write_text("question_no,question\n1,Example\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                pipeline.load_questions(path)

    def test_reviewed_answers_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.csv"
            path.write_text(
                "question_no,rechecked_answer\n9,C\n10,E\n",
                encoding="utf-8",
            )
            self.assertEqual(pipeline.load_reviewed_answers(path), {9: "C", 10: "E"})

    def test_reviewed_answers_reject_invalid_option(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.csv"
            path.write_text("question_no,rechecked_answer\n1,Z\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid reviewed answer"):
                pipeline.load_reviewed_answers(path)

    def test_numeric_unit_match_beats_wrong_unit(self) -> None:
        correct = pipeline.phrase_score("55 km", "The distance is 55 km.")
        wrong = pipeline.phrase_score("55 miles", "The distance is 55 km.")
        self.assertGreater(correct, wrong)

    def test_official_source_is_ranked_above_video(self) -> None:
        official = pipeline.Evidence(
            source="search",
            title="Example",
            snippet="Evidence",
            url="https://example.gov.uk/report",
        )
        video = pipeline.Evidence(
            source="search",
            title="Example",
            snippet="Evidence",
            url="https://www.youtube.com/watch?v=123",
        )
        self.assertGreater(
            pipeline.source_quality_score(official),
            pipeline.source_quality_score(video),
        )

    def test_top_evidence_uses_different_sites(self) -> None:
        row = {
            "question": "What is the example answer?",
            "A": "Alpha",
            "B": "Beta",
            "C": "Gamma",
            "D": "Delta",
            "E": "Epsilon",
        }
        evidence = [
            pipeline.Evidence("search", "Alpha", "Alpha", "https://one.test/a"),
            pipeline.Evidence("search", "Alpha", "Alpha", "https://one.test/b"),
            pipeline.Evidence("search", "Alpha", "Alpha", "https://two.test/a"),
        ]
        selected = pipeline.select_top_evidence(row, "Alpha", evidence, limit=2)
        hosts = {pipeline.urllib.parse.urlparse(item.url).netloc for item in selected}
        self.assertEqual(hosts, {"one.test", "two.test"})

    def test_run_applies_reviewed_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            questions = temp / "questions.csv"
            reviewed = temp / "reviewed.csv"
            output = temp / "submission.csv"
            evidence = temp / "evidence.csv"
            summary = temp / "summary.json"

            questions.write_text(
                "question_no,question,A,B,C,D,E\n1,Example?,One,Two,Three,Four,Five\n",
                encoding="utf-8",
            )
            reviewed.write_text(
                "question_no,rechecked_answer\n1,C\n",
                encoding="utf-8",
            )

            with (
                patch.object(pipeline, "retrieve_evidence", return_value=([], [])),
                patch.object(
                    pipeline,
                    "retrieve_option_evidence",
                    return_value={label: [] for label in pipeline.OPTION_LABELS},
                ),
            ):
                pipeline.run(
                    questions_file=questions,
                    output_file=output,
                    evidence_file=evidence,
                    summary_file=summary,
                    reviewed_answers_file=reviewed,
                    use_web=False,
                )

            with output.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"question_no": "1", "answer": "C"}])


if __name__ == "__main__":
    unittest.main()
