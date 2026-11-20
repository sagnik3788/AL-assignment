# Evaluation plan and scorecard

## Automated evidence

`tests/` checks the router/tool boundary with controlled model replies and exercises the HTTP API against a fresh SQLite database. It covers:

- Correct conditional action selection and structured output.
- Ambiguity causing clarification without a tool call.
- Follow-up context supplied to the router.
- Invalid tool output and model/API failure returning a safe recoverable answer.
- OpenRouter request shape, strict schema mode, and one malformed-JSON retry.
- Session creation, persistence, history retrieval, deletion, request validation, and request IDs.

The committed offline suite should be run with `python -m pytest -q`. It proves application behavior under these fixtures; it does not prove a live model will always make the expected decision.

## Live routing set

`evals/cases.json` includes 15 requests: three each for study plans, explanations, quizzes, answer evaluation, and clarification. Run `python -m evals.run_live` with an OpenRouter key. The report captures expected/actual action, exact action accuracy, non-empty response rate, action-specific structured-output checks, per-request latency, rationale, model, and token counts. The default acceptance target is at least 80% action accuracy, 100% non-empty responses, and 100% valid action-specific structures. Any wrong action or invalid structure should be inspected by case and fixed through examples, clearer instructions, or model selection—not by lowering the threshold without explanation.

## Required multi-step demonstrations

1. **Plan → quiz → feedback:** student gives topic and time constraints; asks for a quiz on a previously discussed topic; answers one question and receives feedback. Check context carryover, no invented time budget, quiz format, and answer relevance.
2. **Clarify → act:** student asks for help preparing but omits subject; assistant asks a short clarifying question; student supplies subject/date; assistant creates an appropriate plan. Check no unsupported assumptions before clarification.
3. **Failure → recovery:** force a timeout or invalid structured response in the test double; assistant returns a retryable error without crashing or returning malformed data; send a valid retry and confirm the workflow resumes.

## Human review scorecard

Review every live case and the three demos. Score each 1–5 and include notes:

| Dimension | Review question |
|---|---|
| Intent | Did it choose the right tool or ask for clarification? |
| Grounding | Is the teaching content factually accurate for the stated topic? |
| Alignment | Does it honor the student's requested level, topic, and time limits? |
| Teaching value | Is the explanation, question, plan, or feedback useful and clear? |
| Safety and tone | Is feedback respectful, age-neutral, and free of unsupported claims about ability? |
| Structure | Does the UI/API expose the expected action and structured fields? |

Record average score, examples of incorrect claims, and model/provider used. Review latency and token use alongside quality; actual dollar cost depends on the selected model and current OpenRouter pricing, so record the usage dashboard or invoice separately. Automated checks do not replace this human review.

## Performance method

The runner reports end-to-end wall time per turn, which includes both router and generation calls. For a deployment performance report, run once after warm-up and record model, network conditions, timestamp, and median/p95 latency. Repeat the fixed set three times to estimate variability. No local fake-model latency should be presented as provider performance.
