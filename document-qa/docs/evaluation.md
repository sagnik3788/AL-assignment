# Retrieval evaluation and current status

## Dataset and measures

`evals/queries.json` contains 15 representative queries over three sample documents. Fourteen queries have a labeled expected source; one asks for information intentionally absent from the entire corpus. Cases cover policy facts, conflicting dates, quantitative results, study limitations, system architecture, privacy, input limits, and citation validation.

`python -m evals.run_eval` uses the configured embedding model and the same chunking and cosine scoring code as the application. It reports:

- **Recall@1 / Recall@5:** share of the 14 answerable queries with an expected source ranked in the first 1 / 5 results.
- **MRR:** mean reciprocal rank of the first expected source.
- **Unknown-answer threshold abstention:** whether the unsupported query's best score is below the configured threshold. A false result means the threshold would send irrelevant evidence to generation.
- Top five sources and scores for each query to make failures diagnosable.

`python -m evals.run_eval --answers` additionally generates answers, records whether citation IDs are valid, and marks support review as pending. A reviewer must compare each answer's claims with its cited passages; valid citation IDs alone do not establish support. This mode makes additional OpenRouter calls and uses API credits.

## Current measured status

The live evaluation has **not been run in this checkout** because no `OPENROUTER_API_KEY` is available locally. The key configured on a Render service is not automatically available to this local evaluation process. No live retrieval score or answer-quality claim is made. After entering the key in `.env`, run the command above and commit or attach `evals/latest-report.json` with the submission.

The offline suite uses deterministic fake embeddings and model responses. It verifies document extraction, chunk boundaries, cosine behavior, session isolation, citations, abstention, duplicate detection, error handling, and deletion. It does not measure real semantic retrieval quality.

## Failure and edge cases covered

1. Malformed PDF, unsupported extension, invalid UTF-8, empty upload, and textless/scanned PDF.
2. Oversized upload, duplicate document, and per-session passage budget.
3. Missing documents and low relevance score; both return abstention.
4. Cross-session document access and deletion; both are denied.
5. Provider timeout/error or invalid structured result; the API returns a sanitized retryable error.
6. A model citation ID not present in retrieved evidence; the response is converted to abstention.
7. Conflicting dates appear in the sample course guide; the model is instructed to report both versions and their source context.

## Improvement loop

Inspect queries with poor rank, then identify whether the miss came from extraction, chunk boundaries, embedding representation, ambiguous wording, or corpus coverage. Change one setting at a time and rerun the same labeled set. Tune the relevance threshold against both answerable and no-answer cases. Add a reranker or hybrid lexical search only if retrieval errors persist; manually review generated answers for evidence support after each retrieval change.
