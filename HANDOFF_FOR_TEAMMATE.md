# BCU AI Hackathon 2026 - Handoff Notes

## Current Status

This repo has been downloaded from:

https://github.com/artidbcu/BCU-AI-Hackathon-2026

Local working path:

```text
C:\Users\Lenovo\Downloads\Coursework_resources-20260417\BCU-AI-Hackathon-2026
```

The original README and checklist have been reviewed. The challenge is to answer 100 MCQs and submit:

- `TEAMNAME_submission.csv`
- source code/notebook
- short README
- short PPTX/PDF presentation
- model/method details, with any LLM capped at 8B parameters

## Work Already Done

Created:

```text
src/generate_submission.py
progress.html
HANDOFF_FOR_TEAMMATE.md
```

Generated/test outputs:

```text
outputs/test_submission.csv
outputs/test_evidence.csv
outputs/test_summary.json
outputs/chunks/submission_001_010.csv
outputs/chunks/evidence_001_010.csv
outputs/chunks/summary_001_010.json
TEAMNAME_submission.csv
outputs/evidence_log.csv
outputs/run_summary.json
```

Important: `TEAMNAME_submission.csv` currently exists but should NOT be treated as final yet. It came from a Wikipedia-only full run that produced a weak answer distribution. The stronger web-enabled chunked run is the direction to continue.

## Pipeline Built So Far

`src/generate_submission.py` does the following:

1. Loads `questions_100.csv`.
2. Cleans common encoding problems in the question text.
3. Builds targeted queries from the question/entity.
4. Retrieves evidence from DuckDuckGo when enabled.
5. Uses Wikipedia search/extract API as fallback evidence.
6. Performs option-specific evidence retrieval for A-E.
7. Scores each option using:
   - phrase match
   - keyword overlap
   - numeric match
   - unit-aware numeric match, e.g. miles vs km
   - question/entity co-occurrence
8. Writes:
   - answer CSV
   - evidence log
   - run summary JSON

## Current Test Result

The latest 5-question web-enabled test produced:

```text
1=B
2=D
3=B
4=D
5=D
```

This looked much better than the starter baseline.

The first 10-question web-enabled chunk produced:

```text
1=B
2=D
3=B
4=B
5=D
6=A
7=E
8=A
9=C
10=B
```

Question 4 was then inspected manually. Evidence clearly said:

```text
U.S. Route 11 in Georgia is 22.8-mile-long (36.7 km)
```

So Q4 should be `D`, not `B`. The script has now been patched with unit-aware scoring, but the 1-10 chunk has not yet been rerun after that patch.

## Setup On Another System

From the repo root:

```powershell
py -m pip install ddgs
```

The script does not require pandas. It mostly uses Python standard library plus optional `ddgs`.

If `py` is not available, use:

```powershell
python -m pip install ddgs
python src/generate_submission.py --start 1 --end 10 --output outputs\chunks\submission_001_010.csv --evidence outputs\chunks\evidence_001_010.csv --summary outputs\chunks\summary_001_010.json
```

## Recommended Next Commands

Rerun the first chunk after the latest scoring patch:

```powershell
py src\generate_submission.py --start 1 --end 10 --output outputs\chunks\submission_001_010.csv --evidence outputs\chunks\evidence_001_010.csv --summary outputs\chunks\summary_001_010.json
```

Then run the remaining chunks:

```powershell
py src\generate_submission.py --start 11 --end 20 --output outputs\chunks\submission_011_020.csv --evidence outputs\chunks\evidence_011_020.csv --summary outputs\chunks\summary_011_020.json
py src\generate_submission.py --start 21 --end 30 --output outputs\chunks\submission_021_030.csv --evidence outputs\chunks\evidence_021_030.csv --summary outputs\chunks\summary_021_030.json
py src\generate_submission.py --start 31 --end 40 --output outputs\chunks\submission_031_040.csv --evidence outputs\chunks\evidence_031_040.csv --summary outputs\chunks\summary_031_040.json
py src\generate_submission.py --start 41 --end 50 --output outputs\chunks\submission_041_050.csv --evidence outputs\chunks\evidence_041_050.csv --summary outputs\chunks\summary_041_050.json
py src\generate_submission.py --start 51 --end 60 --output outputs\chunks\submission_051_060.csv --evidence outputs\chunks\evidence_051_060.csv --summary outputs\chunks\summary_051_060.json
py src\generate_submission.py --start 61 --end 70 --output outputs\chunks\submission_061_070.csv --evidence outputs\chunks\evidence_061_070.csv --summary outputs\chunks\summary_061_070.json
py src\generate_submission.py --start 71 --end 80 --output outputs\chunks\submission_071_080.csv --evidence outputs\chunks\evidence_071_080.csv --summary outputs\chunks\summary_071_080.json
py src\generate_submission.py --start 81 --end 90 --output outputs\chunks\submission_081_090.csv --evidence outputs\chunks\evidence_081_090.csv --summary outputs\chunks\summary_081_090.json
py src\generate_submission.py --start 91 --end 100 --output outputs\chunks\submission_091_100.csv --evidence outputs\chunks\evidence_091_100.csv --summary outputs\chunks\summary_091_100.json
```

## Do Not Use Yet

Avoid this as the final method until improved:

```powershell
py src\generate_submission.py --no-web --output TEAMNAME_submission.csv --evidence outputs\evidence_log.csv --summary outputs\run_summary.json
```

That run completed technically, but the answer distribution was poor: 86 answers were `A`.

## Remaining Work

1. Rerun all 10 web-enabled chunks after the latest scoring patch.
2. Merge the 10 chunk CSVs into one final `TEAMNAME_submission.csv`.
3. Inspect low-confidence rows in the evidence logs.
4. Manually correct obvious misses using the evidence snippets.
5. Rename `TEAMNAME_submission.csv` with the real team name.
6. Write final README.
7. Create final PPTX/PDF presentation.
8. Validate final CSV:
   - exactly 100 rows
   - columns exactly `question_no,answer`
   - answers only A, B, C, D, E

## Practical Warning

The web-enabled run is slower but much better. Chunk 1-10 took about 3 minutes on this system. Full web-enabled generation may take around 25-35 minutes depending on network speed.

