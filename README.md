# BCU AI Hackathon 2026 Team Submission

Team workspace for the BCU AI Hackathon 2026 multiple-choice QA challenge.

## Challenge Summary

The task is to answer 100 multiple-choice questions from `questions_100.csv` and submit a CSV with exactly:

```csv
question_no,answer
1,A
2,C
```

Allowed final answers are `A`, `B`, `C`, `D`, or `E`.

## Current Method

The current pipeline is in:

```text
src/generate_submission.py
```

It uses:

- DuckDuckGo snippets through `ddgs`
- Wikipedia search/extract API
- option-specific evidence retrieval
- deterministic answer ranking using phrase, keyword, numeric, unit-aware, and co-occurrence scoring
- evidence logs for manual review

No organiser answer key is used.

## Model Rule

The hackathon allows any LLM up to 8B parameters.

Current code can run without an LLM and uses retrieval/ranking. A compliant optional LLM arbitration step can be added with a model such as:

```text
Mistral-7B-Instruct
```

Model size: approximately 7B parameters.

## Setup

Install the only optional non-standard dependency:

```powershell
py -m pip install ddgs
```

If `py` is not available:

```powershell
python -m pip install ddgs
```

## Run A Test

```powershell
py src\generate_submission.py --limit 5 --output outputs\test_submission.csv --evidence outputs\test_evidence.csv --summary outputs\test_summary.json
```

## Run In Chunks

Chunked runs are recommended because web search is slower and easier to inspect:

```powershell
py src\generate_submission.py --start 1 --end 10 --output outputs\chunks\submission_001_010.csv --evidence outputs\chunks\evidence_001_010.csv --summary outputs\chunks\summary_001_010.json
```

Continue with 11-20, 21-30, etc.

## Current State

This repo is still work in progress.

The first 5-question web-enabled test gave:

```text
1=B
2=D
3=B
4=D
5=D
```

The first 10-question chunk was run before the latest unit-aware numeric scoring patch, so it should be rerun.

See `HANDOFF_FOR_TEAMMATE.md` for detailed next steps.

