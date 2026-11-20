# Known limitations

- Live model behavior, factual accuracy, latency, and cost still require evaluation with the actual OpenRouter account and chosen model.
- Demo mode exists for offline review and is intentionally heuristic; it is not a substitute for the LLM workflow.
- The app has one shared app access key rather than individual accounts, roles, or per-user ownership. It is suited to a private assessment demo; public multi-user use needs identity and ownership checks.
- The included rate limit is in-process. Multi-replica deployment needs a shared limiter or gateway rules.
- Session content has no automatic retention expiry. Users can delete a session; a real public launch should set a retention policy, backups, and deletion procedures.
- Generated study material can be wrong. It does not cite external sources or guarantee curriculum alignment; students should verify important facts.
- No personalization profile or learning ability inference is stored. The app uses only conversation context and the last topic.
- The UI is a compact web interface and has not had a formal screen-reader or user accessibility study. It uses native controls, labels, keyboard submission, visible focus, and responsive layout as a baseline.
