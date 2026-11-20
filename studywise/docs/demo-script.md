# Demo script

Show the app, `/api/docs`, the action labels, and the `mode` indicator. Explain that demo mode is deterministic and generated answers require the OpenRouter key.

## Scenario 1 — plan, quiz, feedback

1. “I have a biology test in five days. I can study 30 minutes a day. Help me study photosynthesis.”
2. “Quiz me on the topic we just planned.”
3. Answer a question in your own words and ask for feedback.

Explain that the router picks the plan, then uses the previous topic for a quiz, then evaluates the answer. Verify the time budget carries through and the action labels are visible.

## Scenario 2 — clarify before planning

1. “Help me prepare for my test.”
2. Answer the assistant's request for subject and date.
3. Ask it to create the plan.

Explain why the assistant did not infer a subject or date from nothing.

## Scenario 3 — model failure and recovery

1. In the automated test harness, configure the fake OpenRouter client to timeout or return a malformed structured response.
2. Show the safe recovery response and that the API remains healthy.
3. Retry with a valid response and show normal completion.

Do not present a fake failure injected in a test as a real provider outage. State that this case validates the error-handling path.
