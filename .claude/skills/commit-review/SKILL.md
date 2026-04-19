---
name: commit-review
description: The pre-commit workflow for the Diet Management repo. Run this full sequence before every git commit. No exceptions.
---

# Pre-commit review loop

Run this sequence end-to-end before every commit. If any step fails, fix and restart from step 1.

## Step 1 — Formatters and linters

```
ruff format .
ruff check --fix .
mypy --strict .
```

All three must exit clean. `mypy` failures are blocking — do not silence with `# type: ignore` unless you leave a `# reason:` comment explaining why.

## Step 2 — Tests

```
pytest -x
```

Every test passes. New behavior has new tests — if not, hand off to `test-engineer` (or write them following the same standards).

## Step 3 — Invoke the `code-reviewer` agent

Stage the intended files (`git add <paths>` — never `git add .`) and invoke `code-reviewer` on the staged diff.

The reviewer returns either:
- **PASS** — proceed.
- **CHANGES REQUIRED** — fix every blocking item, then restart from step 1.

Do not commit while the reviewer is saying CHANGES REQUIRED. If you disagree with a blocking item, pause and ask the user to adjudicate — do not override the reviewer silently.

## Step 4 — Commit

- Stage only what this commit should contain.
- Use Conventional Commits:
  - `feat(bot): add /plan command`
  - `fix(llm): retry on parse failure at same task class`
  - `refactor(diet): extract meal-scoring helper`
  - `test(storage): cover meal history pagination`
  - `chore: bump anthropic SDK to 0.x.y`
- Subject line ≤ 72 characters.
- Body (optional) explains *why*, not *what*. The diff shows *what*.
- One logical change per commit. If the diff crosses unrelated concerns, split it.

## Step 5 — Do not push without the user's go-ahead

Pushes are shared-state actions. Wait for the user to explicitly say to push. Never force-push.

## Quick reference — failure modes

- Ruff format changed files after you staged → re-stage.
- Mypy complains about a `dict[str, Any]` crossing a boundary → replace with a Pydantic model.
- A test file imports a provider SDK → move to `FakeLLMClient`.
- Reviewer flags a new LLM call as wrong task class → reclassify; don't argue.
- Reviewer flags a direct SDK import outside `llm/` → move it behind `LLMClient`.
