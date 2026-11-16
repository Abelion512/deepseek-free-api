## What changed

<!-- One paragraph: the problem, why this approach, and what a reader should
     hold in their head while reviewing. Link the issue if one exists. -->

Fixes #

## Before / after

<!-- A small table beats prose when behaviour changed. Delete if not useful. -->

| | before | after |
|---|---|---|
| | | |

## Flow (when the change moves data or control)

<!-- GitHub does NOT render Mermaid in comments, and only sometimes in a PR body,
     so the FLOW IS AN IMAGE. Paste the picture, not a code block:
       ![flow](docs/assets/a2a-task-flow.svg)
     Keep the Mermaid source (docs/flows/a2a-task.mmd) in the repo for editing;
     the ASCII copy (docs/flows/a2a-task.txt) is for terminals, not for PRs.
     Delete this section if the change does not move data or control. -->

![flow](docs/assets/a2a-task-flow.svg)

## How it works

<!-- Required. Attach a real image: a screenshot of the result, or a small diagram of how this change works. For config or docs changes, a small accurate diagram of what changes is enough. Do not paste a Mermaid block. Keep the editable source in the repo (for example docs/flows/) so the next person can regenerate the image. -->

## Infographic (always)

<!-- Every PR carries a picture a reviewer can look at without running anything:
     a before/after collage for UI work — `![bar](docs/assets/bar-seating-before-after.png)`
     — the annotated flow for control/data changes, or a screenshot of the
     result for providers and endpoints. Generate it with a checked-in script
     (e.g. scripts/make_bar_infographic.py) so the next person can re-shoot it
     instead of drawing a new one. Text-only PRs are the exception, not the rule. -->

![infographic](docs/assets/bar-seating-before-after.png)

## Verification

<!-- Facts, not adjectives. Paste the command and its result. A live check that
     compares old and new policy is worth more than a passing suite alone. -->

| check | result |
|---|---|
| `python -m pytest -q` | |
| `python -m pyflakes ...` | |
| `node snapgent-extension/test-*.js` | |
| live check | |

## Trade-off

<!-- What this gives up, stated plainly. If nothing, say "none" and why. -->

## Checklist

- [ ] Commits follow Conventional Commits (`fix(scope):`, `feat(scope):`)
- [ ] PR title is the same conventional form as the main commit
- [ ] Only changes related to this fix/feature; no drive-by edits
- [ ] Tests added or updated for the changed behaviour
- [ ] CI is green (`tests`, `e2e`, plus `labeler` on PRs from this repo)
- [ ] Docs updated where behaviour or setup changed — or N/A
- [ ] Review bot findings answered in-thread and fixed in their own commit
