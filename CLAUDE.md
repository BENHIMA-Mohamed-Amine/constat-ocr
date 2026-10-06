# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Execute Explicit Instructions

**When the user gives a clear, actionable instruction, do it. Don't substitute your own process step.**

- An explicit instruction ("create the folder", "do X now") is not a request for re-confirmation, even if a plan or discussion preceded it.
- Don't insert an extra approval/planning/confirmation step out of habit when the ask was already unambiguous.
- Reserve confirmation steps (plan mode, clarifying questions) for genuine ambiguity, multiple valid approaches, or newly-introduced risk — not as a default reflex after any prior discussion.
- If you're unsure whether an instruction is "confirmed enough" to act on directly, that uncertainty itself should be named and asked about - don't silently fall back to a heavier process instead.
- This does not mean comply blindly. If an instruction is technically unsound, a poor fit for the problem, or likely to cause pain later (see Rule 1: Think Before Coding), say so BEFORE starting work — not after. Claude has the right, and the obligation, to push back with the specific reason. Push back once, clearly, then follow the user's call once they've heard it.

## 6. Plan Files for Big Features

**Big features get a tracked plan file. Small fixes don't.**

- For any big feature (new capability, meaningful architectural work, multi-file change), create a markdown plan file inside the project's root-level `plans/` folder before implementing.
- Each plan file has a status, tracked at the top of the file: `proposed` → `approved` → `done`, or `deferred` if paused/shelved.
- When a plan reaches `done`, move its file into a `plans/done/` subfolder — the plan record stays, but out of the active list.
- Small bug fixes and small modifications do NOT need a plan file — this workflow is only for big features. Use judgment; don't create ceremony for a one-line fix.

## 7. Project Structure (Living Section)

**Keep the section below current as the project grows. Additive only — never wipe it.**

- As new files/folders are created, add an entry here with a short one-line description of what it's for.
- If a file's role changes, update its description in place rather than leaving it stale.
- Don't remove an entry just because you're unsure if it's still accurate — check first.

## Project Structure

```
<project-root-folder-name>/
├── backend/           # Python 3.13 project (uv)
│   ├── generator/     # synthetic constat generator: sampled record, drawn on the template, degraded to a phone photo
│   ├── pipeline/      # the extraction pipeline; run.py is the CLI (python -m pipeline.run)
│   │   ├── core/      # shared foundations: config, errors, schema (Record), observability
│   │   ├── data/      # dataset.py (reads the frozen dataset), storage.py (saves each step's output)
│   │   ├── flow/      # graph.py (LangGraph wiring), runner.py (runs the forms)
│   │   ├── refine/     # optional step after the structurer (v4b): FieldRefiner re-reads the hard digit fields from enlarged crops at their template positions
│   │   ├── marks/      # optional step after the LLM: MarksReader reads ticks, tiles, circles and patch from template positions (no model)
│   │   ├── repair/     # optional step after the LLM: Repairer, rules (dates in order, ID and phone formats), registry
│   │   ├── straightening/  # optional step 0: Straightener, registry, OpenCvStraightener (flattens the photo)
│   │   ├── ocr/       # step 1: OcrEngine, the engine registry, columns.py (text grouped by zone), chandra.py (vision model on a server), none.py (reads nothing, for v4a)
│   │   ├── structuring/  # step 2: Structurer, prompts, model and structurer factories, vision.py (v4a: a vision model reads the image and returns the record)
│   │   └── evaluation/   # step 3: scorer, metrics
│   ├── serving/       # Modal + vLLM model servers: deploy/ (one app per model: Chandra, Qwen3.8-27B, ...), query/ (probes against a deployed URL)
│   ├── scripts/       # analyze_run.py (where errors come from), near_misses.py (how close wrong fields are), eval_marks.py (template reader on a split), make_template.py
│   ├── tests/         # unit/, regression/, integration/ (see docs/testing.md)
│   └── assets/        # blank constat template and handwriting fonts
├── data/synthetic/    # the frozen 500-form dataset (manifest and dataset.json tracked, images git-ignored)
├── docs/              # synthetic-data, metrics, pipeline, serving, testing, results-log
├── runs/              # run.json and summary.json of each scored run
├── frontend/          # empty for now
├── _local/            # private: original filled form, story, sample renders (never published)
└── plans/
    └── done/          # completed plan files, moved here once a plan's status reaches `done`
```

## 8. Response Style

**Bullet points. Clear. Concise. Fast to read.**

- Default to bullet points over prose paragraphs.
- Keep each point short — no essays, no padding.
- Answers should be scannable in a few seconds, not read top to bottom like an article.

## 9. Code Quality

**SOLID, clear, idiomatic. One source of truth per fact.**

- Follow SOLID principles — in particular **Open/Closed**: code should be open for extension, closed for modification. New behavior (a new provider, a new format, a new rule) should be addable by adding new code, not by editing existing working code. This is why we use registries/interfaces at extension points instead of `if/elif` chains on type.
- Code should be clear and idiomatic for the language it's written in — follow that language's established conventions and best practices, not patterns borrowed from a different ecosystem.
- **Single source of truth**: any given fact, config value, or piece of logic lives in exactly one place. If updating something requires editing it in more than one file, that's a design smell — refactor so there's one place to change it.
- This section works together with Rule 2 (Simplicity First) — SOLID and DRY are not a license to add abstraction speculatively. Apply them where a real second case, a real extension point, or a real duplication already exists, not in anticipation of one.

## 10. The Meta-Principle

**An agent that understands its own token budget is an agent that never gets stuck.**

Instead of running into context limits unexpectedly, it:
1. Estimates before starting.
2. Checkpoints proactively.
3. Spawns subagents when the task is too large.
4. Reports progress in terms humans can understand: "I'm at 60% context, 40% task complete, spawning 2 subagents for the remaining work."

This is what separates agents that can run autonomously for hours from agents that silently degrade and fail.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
