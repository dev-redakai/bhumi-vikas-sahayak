Add a rule amendment published after 06-03-2025.

Input: $ARGUMENTS (notification date, sub-rule, source URL).

1. Read the source. Record only what it says; mark secondary sources in `verification`.
2. Append an object to `data/amendments.json` (id `YYYY-MM-DD-rule-x-y-z`, rule, sub_rule, date, title, summary, summary_hi, affects_rules, triggers, anchor, sources, verification).
3. Add a test in `tests/test_agent.py` asserting the amendment is attached for a matching question.
4. Run `/eval`. Update the README "What works" section.
