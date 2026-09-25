# Resolve AI Coach

An in-DAW AI teaching assistant for DaVinci Resolve. Unlike copilots that
execute edits for you, this project reads project state (read-only) and a
user's typed question, then explains the relevant tool/technique — it
never calls Resolve's write API.

Originally authored as a Color-page-only coach, this repository is being
expanded to support the entire DaVinci Resolve application (Cut, Edit,
Fusion, Color, Fairlight, Deliver). The core product promise remains the
same: local, privacy-friendly, retrieval-augmented guidance over an authored
knowledge base — no external API calls required at query time.

## Core rule (do not violate)

The coach engine MUST NOT call Resolve's write API. It has read-only access
to project state (timeline, node graphs, clip metadata, Fairlight session
state, Fusion comps, Deliver settings) via the scripting API only. If a
feature requires writing to the project, stop and flag it as a suggestion
rather than implementing it automatically.

This constraint preserves user safety, prevents accidental project changes,
and clarifies product behavior for users and reviewers.

## Goals and scope

- Provide actionable, page-aware guidance across the entire Resolve UI:
  Cut, Edit, Fusion, Color, Fairlight, and Deliver.
- Match user questions by meaning using a small, hand-authored knowledge
  base (symptoms → diagnosis → steps) plus retrieval and a local LLM.
- Keep everything local and offline-capable: embeddings, index, and LLM can
  run on-device (llama.cpp, GGML-style runtimes, or equivalent).
- Make the coach usable inside Resolve as a docked panel (or Scripts menu
  fallback on Free) so answers are contextualized to the currently open
  project and page.

## How this works (overview)

1. Content (`content/entries/*.yaml`) — hand-authored symptom → tool →
   explanation entries. This is the trusted knowledge base; entries target a
   page and specific context (e.g., Color node tree, Edit timeline markers,
   Fusion node connections, Fairlight mixer routing).
2. Indexing (`scripts/build_index.py`) — embed each entry (mainly
   `symptom_phrases` + `diagnosis`) into a local vector store so questions
   are matched by meaning, not keyword. Indexing is an offline build step.
3. Project state layer (`src/resolve_state.py`) — reads Resolve's scripting
   API and converts page-specific state into short factual statements that
   disambiguate which entry applies (e.g., "Color: node 3 active, primary
   sat = 85", "Edit: multicam angle 2 enabled at playhead"). Implementations
   will be page-specific modules behind a common interface.
4. Coach engine (`src/coach.py`) — takes the user's typed question + project
   state facts + retrieved entries and produces an explanation via a local
   LLM. The engine enforces the core rule and formats guidance as steps and
   rationale. It also surfaces 'suggested automated action' when appropriate
   but never executes it.
5. UI — docked panel inside Resolve (preferred) showing question entry,
   matched symptoms, suggested steps, and expandable detail. For Resolve
   Free, the Scripts-menu approach remains supported (output to Resolve
   Console) as a fallback.

## Project structure

```
resolve-ai-coach/
├── content/
│   ├── schema.yaml           # required fields for every entry
│   └── entries/*.yaml        # the authored knowledge base (page-tagged)
├── import_scripts/           # Resolve integration and state probes
├── src/
│   ├── validate_entries.py   # checks entries against schema
│   ├── resolve_state.py      # read-only Resolve state adapter
│   ├── edit_state.py         # Edit-page state snapshot
│   ├── retriever.py          # authored-entry retrieval
│   └── ollama_client.py      # optional local LLM client
├── scripts/
│   ├── build_index.py        # builds a local index from authored entries
│   └── import_manual.py      # optional manual-corpus import tool
├── tests/
│   └── test_edit_state.py
├── requirements.txt
└── README.md
```

This repository copy intentionally excludes the large DaVinci Resolve manual
corpus, extracted page text, generated manual indexes, PDFs, Python caches,
and local model files. Those assets are source material for optional indexing
and are not required to review or develop the application code.

## LLM backend: cloud (temporary) vs. local

Generation currently defaults to a **free cloud API (Groq)** instead of a local
Ollama model, since local inference is heavy for older machines. This is meant
to be temporary — the switch back to fully local/offline is a one-line change.

- `src/cloud_client.py` — calls Groq's free-tier API (OpenAI-compatible).
- `src/ollama_client.py` — original local Ollama client (untouched, for later).
- `src/llm_client.py` — the switch. Both `resolve_coach.py` and
  `resolve_coach_ui.py` import `generate_answer` from here, not from a specific
  backend, so nothing else needs to change when you switch.

**Setup (cloud, current default):**

1. Get a free API key at https://console.groq.com/keys (no credit card required).
2. Set it as an environment variable before running the coach:
   - Windows (persistent): `setx GROQ_API_KEY "your-key-here"` (restart Resolve after)
   - Windows (current session only): `set GROQ_API_KEY=your-key-here`
3. Run as usual — `MULTIMEDAI_LLM_BACKEND` defaults to `cloud`, so no extra config needed.

**Switching back to local later:**

1. Install Ollama and pull a model: `ollama pull llama3.2:3b`.
2. Set `MULTIMEDAI_LLM_BACKEND=local` as an environment variable.
3. That's it — `llm_client.py` will route to `ollama_client.py` instead.

Free-tier note: Groq's free plan is rate-limited (roughly 30 requests/min,
capped daily tokens depending on model) but requires no card and doesn't
expire. If you hit limits, Google AI Studio's Gemini free tier is a solid
alternative and could be added as another backend the same way.

## Getting started (developer)

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Validate all authored entries before indexing or running the coach:

```bash
python src/validate_entries.py
```

3. Build an entry index when needed:

```bash
python scripts/build_index.py --content content/entries --out data/index.bin
```

4. Run the project-state reader inside Resolve (see the "Running" section
   below) to confirm page-specific state extraction works in your setup.

## Current status (summary)

- [x] Content schema defined
- [x] Validator script
- [x] 5 starter entries (Color-related starters)
- [x] Prototype Resolve scripting read layer for Color (needs live testing)
- [ ] Expand content to cover all Resolve pages (see Roadmap targets)
- [ ] Implement `scripts/build_index.py` and local vector store
- [ ] Implement `src/coach.py` with LLM orchestration and prompt safety
- [ ] Docked panel UI (Resolve integration) and Scripts-menu fallback

## Roadmap — from Color-only to full Resolve coach

This roadmap is intended to be pragmatic: short iterative phases with
clear deliverables, tests, and evaluation criteria.

Phase 0 — Stabilize (1–2 weeks)
- Goal: make the existing Color-page experience robust and reproducible.
- Tasks:
  - Validate current entries and fix schema issues.
  - Add automated entry linting to `validate_entries.py` (if missing).
  - Smoke-test `src/resolve_state.py` in Resolve Free via Scripts menu.
- Deliverables: All Color starter entries validated, resolve_state prints
  deterministic facts for a sample project.

Phase 1 — Multi-page project-state adapters (2–4 weeks)
- Goal: add page adapters for Edit and Deliver (highest-impact pages), plus
  a common interface.
- Tasks:
  - Implement `src/resolve_state/edit.py` and `src/resolve_state/deliver.py`.
  - Define common fact shape (page, key, value) and unit tests for adapters.
  - Add sample entries for Edit/Deliver to `content/entries/`.
- Deliverables: Adapter unit tests passing and manual test in Resolve Free
  showing extracted facts for Edit and Deliver pages.

Phase 2 — Indexing and retrieval (2–3 weeks)
- Goal: implement `scripts/build_index.py`, an on-disk vector store, and a
  retrieval layer used by the coach.
- Tasks:
  - Choose an embedding library (local models or small Python wrapper).
  - Implement index build and simple nearest-neighbor retrieval.
  - Add integration tests for retrieval accuracy on a held-out set of
    symptom queries.
- Deliverables: `data/index.*` files + retrieval API and test coverage.

Phase 3 — Coach engine (3–4 weeks)
- Goal: assemble project-state facts + retrieval results into a prompt that a
  local LLM can answer reliably and safely.
- Tasks:
  - Implement `src/coach.py` with prompt templates and safety checks.
  - Support pluggable LLM backends (llama.cpp, local REST server, optional
    remote API behind a config flag — but default offline).
  - Add evaluation harness (example queries + expected answer attributes).
- Deliverables: Coach can produce explanations for a set of example queries
  from Color, Edit, and Deliver.

Phase 4 — Fusion & Fairlight, UX, and polish (4–6 weeks)
- Goal: add Fusion and Fairlight adapters, build the docked panel UI, and
  finalize authoring guidance.
- Tasks:
  - Implement `src/resolve_state/fusion.py` and `fairlight.py` adapters.
  - Build Resolve panel UI (Python/HTML or Python-only depending on API).
  - Expand content authoring guide and recruit content reviewers.
- Deliverables: Docked panel prototype, 80–150 validated entries per page,
  and a documented release checklist.

Phase 5 — Release & documentation (2 weeks)
- Goal: make a public local build with clear install/run docs, contributor
  docs, and evaluation results.
- Tasks:
  - Finalize README, docs, and packaging notes.
  - Create demo projects and user tests.
- Deliverables: Release candidate, docs, and sample projects.

Notes on timelines: estimates assume 1–2 full-time contributors. Adjust
based on team size and available test devices (Resolve Free vs Studio).

## Running `resolve_state.py` — how to run in different setups

### Resolve Free (Windows) — recommended for development and manual tests

Because Resolve Free does not reliably accept external Python processes,
scripts must be run inside Resolve's embedded Python environment via the
Scripts menu:

1. Copy the relevant page-adapter script (or a wrapper that prints facts)
   into Resolve's Scripts folder:

```
%APPDATA%\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\
```

2. Create a simple wrapper (optional) that imports your module and prints
   facts to the Console. Place that wrapper in the same folder.
3. Open Resolve, open a project and a page with content (Edit, Color,
   Fusion, etc.), then run Workspace → Scripts → <your script name>.
4. View output in Workspace → Console.

This ensures the script runs inside Resolve's Python where
`DaVinciResolveScript` is importable.

### Resolve Studio (external scripting)

If you have Resolve Studio with External Scripting enabled:

```
python src/resolve_state.py
```

Ensure Preferences → System → General → External scripting using is set and
that environment paths in `_configure_environment()` (in the adapter) match
your install.

## Content authoring guidance (summary)

- Each entry must target a page (field: `page`) and include symptom
  phrases, a diagnosis block, and step-by-step guidance. See
  `content/schema.yaml` for details.
- When adding non-Color entries, prefer small, testable examples (one
  symptom per entry) that reference concrete UI elements or API facts.
- Always run `python src/validate_entries.py` after editing content.

## Testing and evaluation

- Unit tests for page adapters should run against mocked Resolve API objects
  where possible.
- Retrieval and coach evaluation should include a small held-out set of
  user-like queries and expected answer attributes (page, whether it needs
  a node edit, etc.).
- Human-in-the-loop QA: reviewers (domain experts) should validate a sample
  of generated answers for accuracy and usefulness before large-scale
  content expansion.

## Working with Copilot in this repo

- When authoring entries, point Copilot at an existing entry in
  `content/entries/` that matches the target page as an example and at
  `content/schema.yaml` for required fields.
- Use Copilot to help regenerate or fix entries flagged by
  `validate_entries.py` but treat the validator as the source of truth.
- For page adapters, use Blackmagic's Developer docs to verify API calls —
  Copilot's suggestions must be validated against those docs and live
  testing.

## Contributing

- Add issues for page adapters, indexing, or coach features and follow the
  roadmap. Small PRs that add entries or tests are the best way to get
  started.
- When adding new code that depends on external Resolve behavior, include
  instructions for how to test it in Resolve Free (Scripts menu) and a
  sample project if possible.

---

This README expands the original Color-focused plan into a multi-page,
iterative roadmap and includes concrete deliverables and developer-facing
instructions. If this looks good, next recommended actions:
- Run `python src/validate_entries.py` to find content issues (quick win),
- Or ask to implement a starter `scripts/build_index.py` so indexing can
  begin.
