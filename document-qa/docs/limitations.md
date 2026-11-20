# Known limitations

- The live embedding evaluation has not yet run in this checkout; real retrieval quality and answer support remain unmeasured until `OPENROUTER_API_KEY` is configured locally and the evaluation is executed.
- OCR, scanned PDFs, handwriting, tables, complex multi-column layouts, and password-protected files are unsupported.
- The initial word-based chunker can split semantic units and can create repeated overlap text. The fixed query set should guide any chunking changes.
- The cosine threshold is a starting point, not a calibrated confidence score. Similarity measures semantic proximity, not factual entailment.
- The model may make unsupported claims even when it cites a retrieved chunk. The app validates citation membership but does not prove claim-level entailment.
- Conflicting evidence is surfaced through prompting and citations, not a deterministic conflict-resolution policy.
- Extracted text, embeddings, and chat history remain in PostgreSQL until the user deletes the desk or an operator removes data. There is no automatic retention expiry, account identity, or account-level recovery.
- A session UUID is an unguessable resource identifier, not authentication. Anyone with the ID can access that desk. Do not use the public assessment demo for confidential documents.
- The rate limit is process-local; the PostgreSQL JSON-vector scan is capped at 2,000 chunks per desk. Larger or multi-instance use needs shared rate limiting and indexed vector search.
- OpenRouter availability, provider limits, and model behavior can affect requests. Generation/embedding calls return bounded, sanitized errors; there is no offline answer mode.
- Render free services may sleep, restart, and use expiring free Postgres. The blueprint is for assessment review, not long-term production retention.
