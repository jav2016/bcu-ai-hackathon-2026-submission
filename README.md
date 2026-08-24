# BCU AI Hackathon 2026 | Evidence-Grounded Question Answering

This repository contains my BCU AI Hackathon 2026 submission. The challenge was to answer 100 multiple-choice questions in four hours and submit the answers in a CSV.

## What I built

A Python pipeline that:

- cleans the supplied questions;
- searches DuckDuckGo and Wikipedia for evidence;
- scores each answer option;
- records a ranking score and source links;
- flags uncertain cases for manual review.

The final run used evidence retrieval and deterministic scoring, not an LLM. The ranking score helps identify weak answers; it is not an accuracy percentage. I did not use the organiser answer key.

## Workflow

Question -> evidence search -> option scoring -> ranking check -> manual review -> final CSV

## Result

- 100 questions processed
- 100 valid answers
- 4 manual corrections
- 12 cases retained in the recheck log

The reviewed answers are applied automatically when the script runs. Official accuracy is not claimed because no answer key was used.

## Run

```powershell
pip install -r requirements.txt
python src/generate_submission.py
python -m unittest discover -s tests -v
```

The script creates `generated_submission.csv` and keeps the checked final file unchanged.

Main files: `src/generate_submission.py`, `Anthropic_submission.csv` and `outputs/recheck_flags_v2.csv`.

