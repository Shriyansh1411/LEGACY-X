# LEGACY-X

LEGACY-X is an agentic modernization platform for legacy software. It is designed to take an older codebase, understand the business behavior embedded in it, translate that logic into a modern implementation, verify that the rewritten output still behaves correctly, and explain the root cause and remediation path in a way that is understandable to engineers and stakeholders.

The project is built as a product-style workflow around an AI-driven modernization agent. Instead of treating modernization as a single one-shot prompt, it breaks the task into explicit stages: ingest, analyze, understand, generate, verify, and explain. This keeps the workflow interpretable, debuggable, and aligned with real engineering practice.

## Why this exists

Legacy systems often carry important rules in a form that is hard to reason about: older syntax, hand-built business logic, unclear control flow, limited test coverage, and little architectural clarity. LEGACY-X gives teams a way to:

- ingest a legacy source tree and normalize it into a traceable project record
- extract the language and control-flow signals in the code
- map behavioral intent into a blueprint of rules, dependencies, and edge cases
- generate a modernized implementation using an LLM-backed workflow
- verify the generated output against the original behavior
- explain why the legacy logic existed and what should be changed in the modernization process

This makes the product feel like a modernization copilot or agentic workflow rather than a static demo.

## Product workflow from the user perspective

1. Upload a legacy project or source files.
2. Review the ingested manifest and source preview.
3. Run the analysis step to detect legacy patterns, business rules, and control-flow signals.
4. Run the understanding stage to build the behavioral blueprint and dependency model.
5. Trigger the agentic generation step to produce a modern Python implementation.
6. Review verification results to confirm whether the modern output matches the legacy behavior.
7. Inspect the explanation board that describes the root cause, confidence, and suggested remediation.

The UI supports a modern/legacy toggle so the user can compare the original behavior and the transformed result side by side in a product-style dashboard.

## User perspective workflow

The product experience is intentionally designed as a guided modernization workflow for a real engineer working on a legacy system:

1. Start with a legacy codebase and upload the relevant files.
2. Let the system ingest the project and show the extracted manifest, source preview, and file inventory.
3. Review the analyzer output to understand the language, signals, and rules that are present in the legacy code.
4. Move into the understanding stage, where the app maps business logic, control flow, rules, and dependencies into a structured behavioral blueprint.
5. Trigger the agentic generation step to create a modern implementation from the legacy logic.
6. Inspect the verification view to compare the old behavior with the generated modern code and catch mismatches early.
7. Use the explanation layer to understand the root cause, confidence, and suggested fix before shipping the migration.

This makes the tool feel like a guided modernization agent rather than a static code converter. The user is always in control of the workflow, while the system provides structured insight at every stage.

## Agentic architecture

The system is intentionally structured as a staged agent workflow:

- Ingest: collect project files and build a manifest
- Analyze: detect language patterns, signals, and business rule density
- Understand: infer behavior, dependencies, and edge cases
- Generate: translate legacy logic into modern Python using an OpenAI-compatible model
- Verify: compare legacy output with modern output
- Explain: summarize the change, root cause, and suggested fix

This staged design makes the modernization process observable, safer, and easier to trust than a black-box rewrite.

## Tech stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI
- Database: PostgreSQL + pgvector
- Containerization: Docker Compose
- AI layer: OpenAI-compatible API via environment-driven configuration
- Validation: pytest-based backend checks

## Project structure

- `frontend/` – dashboard UI and product experience
- `backend/` – FastAPI app, schemas, services, models, and API routes
- `docker-compose.yml` – container orchestration for frontend, backend, and database
- `backend/.env` – local runtime config for API and DB
- `backend/.env.example` – sample environment configuration

## Local setup

### Start the project

```bash
docker compose up --build
```

This starts:

- Frontend on `http://localhost:5173`
- Backend API on `http://localhost:8001`
- PostgreSQL on `localhost:5433`

### Run the workflow

1. Open the frontend.
2. Upload a legacy codebase.
3. Run the analysis stage.
4. Run the understand step.
5. Trigger modern code generation.
6. Validate with verification.
7. Review explain output and root-cause summary.

## Environment configuration

Create or update the backend environment file:

```bash
cp backend/.env.example backend/.env
```

Then configure values like:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
DATABASE_URL=postgresql+psycopg://legacyx:legacyx@db:5432/legacyx
```

If an API key is not available or the provider is rate-limited, the app falls back to a deterministic, safe generation path so the workflow remains usable.

## Development notes

- The UI is designed as a dark, product-focused modernization dashboard.
- The backend exposes pipeline endpoints under `/api/projects/...`.
- The system emphasizes explainability and verification over blind auto-generation.
- The implementation is intentionally modular so each stage can be improved independently.

## Useful commands

```bash
# rebuild all services
docker compose up -d --build

# view logs
docker compose logs -f api frontend

# run backend tests
cd backend && PYTHONPATH=/app pytest tests/test_ingest_api.py -q
```

## Summary

LEGACY-X is meant to feel like an AI-assisted modernization agent for enterprise legacy systems: it ingests the old code, understands the behavior, translates it into a modern implementation, checks correctness, and explains the result. The goal is not just code conversion, but controlled, trustworthy modernization that engineers can review, reason about, and ship with confidence.

