# Technical decision log

## 1. Conditional workflow instead of an open-ended agent loop

**Decision:** a structured router selects one action, and the application dispatches to one of four study tools or clarification. Each turn makes at most two model calls.

**Alternatives:** fixed sequential pipeline; open-ended LangGraph/LangChain agent loop.

**Reason:** requests have a small known set of capabilities. Explicit routing satisfies the agentic-workflow requirement while keeping tool selection inspectable, execution bounded, failures easy to recover from, and no extra orchestration dependency necessary. A graph framework is justified if the workflow later gains resumable long-running tasks or many branching steps.

## 2. OpenRouter-compatible structured output plus local validation

**Decision:** call OpenRouter's chat-completions endpoint using a configurable model, temperature zero, and strict JSON Schema output; validate the route with Pydantic and validate generated fields in application code. The default is `google/gemini-2.5-flash-lite`, a lower-cost model that currently supports OpenRouter's JSON Schema `response_format`; change it through configuration if live evaluation favors another model. Pricing and model availability can change. Plans must match the requested day count and daily time ceiling; quizzes must contain exactly three questions. Use bounded timeouts and one retry for transient or malformed JSON responses.

**Alternatives:** parse free-form text; hard-code a single provider SDK; rely on prompting alone.

**Reason:** provider/model flexibility is requested, while structured routing makes conditional logic reliable. Application-side checks are still necessary because endpoint support and generated output can vary. A failed response stops safely rather than silently routing to a guessed action.

## 3. PostgreSQL with explicit Alembic migrations

**Decision:** persist sessions and messages in PostgreSQL in the Compose deployment; use SQLAlchemy and migrations. SQLite remains the zero-setup local development/test option.

**Alternatives:** in-memory chat state; JSON files; SQLite-only deployment.

**Reason:** sessions must survive restarts and support deletion. Relational constraints and migrations give a clear schema lifecycle; SQLite keeps the local path simple. Production uses the database service and persistent volume.

## 4. Bounded context and explicit deletion

**Decision:** store full conversation history but send only the configured recent window and compact state to the model. Provide a delete endpoint and a UI reset action.

**Alternatives:** send every historical message on every turn; retain no server-side history.

**Reason:** a bounded prompt limits latency and cost while preserving continuity for ordinary follow-ups. Server-side history enables refresh recovery and evaluation; deletion gives users control over stored study text.

## 5. Dashboard visual language

**Decision:** use a warm off-white canvas, yellow blocks, strong black outlines, and compact status cards for the learning workspace. This visual direction is inspired by the public [Zerch project](https://github.com/sagnik3788/Zerch); the Studywise page is implemented independently.
