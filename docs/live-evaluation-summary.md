# Live evaluation summary

## Completed run

On 20 November 2026, all 15 evaluation prompts completed against `google/gemini-2.5-flash-lite` using OpenRouter. Routing accuracy was **15/15 (100%)** and every response was non-empty. Observed end-to-end latency was approximately **2.83 s mean**, **3.0 s median**, and **4.1 s p95**. These values come from the runner's per-case console output and represent one run under the network conditions at that time.

The completed run happened before the runner added its action-specific structured-output metric. The runner exited successfully under its then-current acceptance checks. A later attempt to add that metric completed only one case before OpenRouter returned HTTP 402 (Payment Required); [incomplete-live-report.json](../evals/incomplete-live-report.json) records that incomplete attempt and its fallback responses. It is not a valid routing score. Add OpenRouter credits or enable billing, then rerun `python -m evals.run_live` to generate a fresh full report with structure and execution-failure checks.

Automated routing and shape checks do not verify factual accuracy or teaching quality. Human review is still required using the scorecard in [evaluation.md](evaluation.md).
