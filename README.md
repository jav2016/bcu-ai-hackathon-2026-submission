# BCU AI Hackathon 2026 Submission

This is my work for the BCU AI Hackathon 2026 task.

The task was to answer 100 multiple choice questions and submit the answers in a CSV file.

## Files

- `questions_100.csv` - given questions
- `Anthropic_submission.csv` - my final answers
- `src/generate_submission.py` - code used to search and score answers
- `outputs/recheck_flags_v2.csv` - questions I checked again because they were risky

## How I did it

I used Python to search for evidence from web/Wikipedia and compare it with the answer options. After that I manually checked the risky answers because some first answers were not reliable.

I did not use the organiser answer key.

Important recheck fixes:

- Q9 = C
- Q10 = E
- Q88 = E
- Q95 = B

The final CSV has 100 rows and only A, B, C, D or E answers.
