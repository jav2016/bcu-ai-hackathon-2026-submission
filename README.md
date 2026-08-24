# BCU AI Hackathon 2026 | Evidence-Grounded Question Answering

This repository contains my BCU AI Hackathon 2026 submission. The challenge was to answer 100 multiple-choice questions in four hours and submit a reproducible CSV.

## What I built

A Python pipeline that:

- cleans the supplied questions;
- searches DuckDuckGo and Wikipedia for evidence;
- scores each answer option;
- records confidence and source links; and
- flags uncertain cases for manual review.

The final run used evidence retrieval and deterministic scoring, not an LLM. I did not use the organiser answer key.

## Workflow

Question -> evidence search -> option scoring -> confidence check -> manual review -> final CSV

## Result

- 100 questions processed
- 100 valid answers
- 4 manual corrections
- 12 cases retained in the recheck log

Official accuracy is not claimed because no answer key was used. Unclear questions were checked manually instead of being accepted without evidence.

## Run

```powershell
pip install -r requirements.txt
python src/generate_submission.py
```

Main files: `src/generate_submission.py`, `Anthropic_submission.csv` and `outputs/recheck_flags_v2.csv`.

