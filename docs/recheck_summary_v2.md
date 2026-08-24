# Manual Recheck Notes

The first generated answers included some weak or unclear cases.

`Anthropic_submission.csv` is the final reviewed file. Running the script creates `generated_submission.csv` and automatically applies the checked answers in `outputs/recheck_flags_v2.csv`.

Use the recheck log to see the 12 questions reviewed by the team and the reason for each decision.

Main corrections: Q9 changed to C, Q10 changed to E, Q88 changed to E, and Q95 changed to B.

High risk questions: Q28, Q32, Q39, Q43, Q52, Q55, Q65, Q79, and Q95.

Some of these are not simple hallucinations. A few questions have bad or unclear options. For example, Q79 asks which village is not part of Rachitova commune, but all listed villages appear to be part of it. For these cases, we chose the closest answer but marked the issue in the flags file.

These decisions are documented for transparency. They are not presented as official answers because no organiser answer key was used.
