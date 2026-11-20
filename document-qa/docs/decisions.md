# Technical decision log

## 1. Selectable-text PDF and TXT; OCR deferred

**Decision:** Support PDFs with extractable text and UTF-8 TXT. Reject image-only/scanned PDFs with an explicit OCR message.

**Reason:** This demonstrates extraction, retrieval, citations, and failure behavior without introducing a large OCR runtime or inaccurate silent fallbacks. pypdf gives page-level provenance. The supported scope is explicit and testable.

**Alternative:** OCR every page, or run OCR only when extracted text is sparse. OCR increases latency and compute, adds language/layout errors, and needs a quality evaluation set. Add it when scanned documents are a required user workflow.

## 2. Word-window chunks with overlap and source pages

**Decision:** Split each page into 180-word windows with 30-word overlap; never merge across page boundaries.

**Reason:** Page-aware chunks keep citations precise, while overlap reduces the chance a fact split at a boundary loses context. A fixed word budget is deterministic, cheap, and inspectable.

**Alternative:** Recursive semantic/token chunking or paragraph-level chunks. Those can preserve structure better, but require a tokenizer or layout heuristics and add tuning. Compare them on the labeled retrieval set before changing defaults.

## 3. OpenRouter embeddings plus PostgreSQL JSON vectors for the first release

**Decision:** Use `openai/text-embedding-3-small` at 512 dimensions through OpenRouter, persist vector arrays with chunks in PostgreSQL, and use cosine similarity in the app.

**Reason:** One server-side key configures both embeddings and generation; dimension reduction limits storage. PostgreSQL makes uploads survive Render restarts, unlike a local FAISS index or SQLite file on a free service. The app caps a desk at 2,000 chunks, keeping a linear cosine scan appropriate for the assessment/demo scale.

**Alternatives:** Local sentence-transformers and FAISS reduce per-query provider calls but add model download/image size and CPU memory. Chroma is convenient but adds a stateful vector service/directory. pgvector gives indexed nearest-neighbor search but adds extension and index tuning. Move to pgvector after latency or corpus measurements exceed the current cap.

**Cost choice:** The current OpenRouter model cards list Gemini 2.5 Flash Lite at $0.10/M input and $0.40/M output tokens and text-embedding-3-small at $0.02/M tokens; prices can change. See [chat model pricing](https://openrouter.ai/google/gemini-2.5-flash-lite/pricing) and [embedding model pricing](https://openrouter.ai/openai/text-embedding-3-small/providers).

## 4. Deterministic relevance gate before LLM generation

**Decision:** If the best cosine score is under `MIN_RELEVANCE_SCORE`, return a no-answer response without calling the chat model. Start at 0.28 and measure/calibrate on the included query set.

**Reason:** This avoids spending generation tokens when retrieval appears weak and makes one abstention boundary observable in evaluation.

**Alternative:** Always ask the model to decide whether context is sufficient. That may help on borderline cases, but adds cost and still relies on model judgment. A calibrated classifier or reranker can be compared if evaluation shows threshold errors.

## 5. Strict structured answers with server-validated citation IDs

**Decision:** Ask for JSON Schema output containing answer, abstention flag, and source IDs; discard IDs that were not in the retrieved passages, and abstain if no valid source remains.

**Reason:** Structured parsing makes failure visible, and server validation prevents citations to nonexistent passages. The model is instructed to surface conflicts and avoid outside knowledge.

**Limit:** Citation membership is not a proof of entailment. Human review and answer-support metrics are required; add claim-level entailment evaluation only if the manual evaluation finds repeated unsupported claims.
