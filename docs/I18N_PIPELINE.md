# i18n pipeline: translate new repos, polish copy

Runs inside `python3 tools/update_stars.py --slot ...` (the daily workflow and `tools/local_daily.sh`), after the ranking is
discovered and before the READMEs are rendered. Skip it with `--no-i18n`. Polish can also be run on its own: `tools/polish_local.sh`.

```
discover new repos ─▶ 1 translate (only what is missing) ─▶ [2 polish, local only] ─▶ render
```

Everything here is **fail-safe**: no key / sign-in, no CLI, model not offered, a failed call, a reply that breaks a guard — the
existing text stays and the scheduled update carries on (`run_safe` swallows any error; the exit code never changes).

## 1. Translate

`data/newcomer_i18n.json`: `{ "owner/repo": { "src": "<description it was translated from>", "zh-Hans": ..., "zh-Hant": ..., "ja": ..., "ko": ..., "en": ... } }`.
`en` is only needed when the source contains CJK text. The README shows a translation only while `src` equals the live description.

For the top 20 of every category (what the READMEs show) the pipeline lists the gaps (`translation_gaps`): no entry,
a stale `src`, or a missing language. Already translated entries are never sent again. New translations are written
after every batch of 8 repos. A translation is accepted only if it is one plain line and keeps every number of 2+ digits and
every identifier-like name (`TinyPNG`, `gpt-2`, `Node.js`...). Rules sent to the model: add no facts, remove no facts,
keep names/links/code/emoji/`…`, star = 星标 (zh-Hans) / 星號 (zh-Hant), agent = 智能体 / 代理 / エージェント / 에이전트,
Traditional Chinese in Taiwan/Hong Kong wording.

## 2. Polish

Voice: plain spoken words, short-video host style, lead with the point, one sentence for what it does and why it is
worth a look, condensed, never clickbait, never exaggerated, nothing invented.

Polished by default: the project blurbs (`data/projects.json`, all five languages) and the translated new-repo
descriptions. Category descriptions (`data/categories.json`) are short taxonomy labels, so they are polished only on request
(`--targets categories`). Never polished: suspected cracked/pirated repos (they stay literal), UI strings in `tools/i18n.py`,
and the repo's own original description (`src`, it is not ours).

Each text is polished once. `data/polish_state.json` stores, per `kind|name|lang`, the hash of the text as it is now; the
same text is never sent twice, an edited or re-translated text is polished again, and a text whose polish was rejected 3
times is left alone until it changes. Bump `POLISH_VERSION` in `tools/i18n_pipeline.py` after changing the style prompt to
polish everything again. Delete `polish_state.json` for the same effect.

A polished text replaces the old one only if `check_polished` passes. It is rejected when it: is empty or multi-line; is longer
than the original (+30%) or drops more than 65% of it; changes any number; loses a Latin name/word of the original (English: names,
identifiers and capitalised words; other languages: every Latin word) or adds a new identifier; adds `!` or hype words
(炸裂, 颠覆, 震惊, game-changer, ...); loses a trailing `…` or `：`. On rejection the previous text stays.

## Who runs what

| Stage | Where | Tool | Credentials |
|---|---|---|---|
| translate | CI (`daily-update.yml`) and locally | Cursor CLI in CI; `agy` locally | CI: repository secret `CURSOR_API_KEY` (optional; without it translation is skipped). Local: your signed-in `agy` |
| polish | **your machine only** | Google Antigravity CLI `agy` | your signed-in `agy` session; nothing in the repo or in CI |

CI never polishes. `tools/update_stars.py` polishes only when `I18N_POLISH=1`, which `tools/local_daily.sh` sets (turn off with `I18N_POLISH=0`).
Because CI keeps translating new repos, a freshly translated description is shown as translated-but-unpolished until the next local polish run.

## Model

- Default **`gemini-3.8-flash-medium`** (`POLISH_MODEL`; translation uses it too unless `I18N_TRANSLATE_MODEL` is set). Antigravity lists it as
  `Gemini 3.8 Flash (Medium)` (`-high` also exists). Cursor uses the same slug.
- Before use the CLI's model list (`agy models` / `agent --list-models`) must contain that exact slug. If it does not, the stage is skipped
  and the log names the models that are available. **No other model is ever substituted.** (agy headless mode itself also exits non-zero
  on an unknown `--model` instead of falling back.)
- Calls: `agy -p <prompt> --model <slug> --output-format json --print-timeout 4m --disable-slash-commands`, run in an empty temp directory,
  so the agent cannot see the repo; tools that need approval are soft-denied in headless mode. `GITHUB_TOKEN` and `CURSOR_API_KEY` are removed
  from the agent's environment.
- Limits: `I18N_BUDGET_SEC` (default 900) caps the time per run; 3 failed calls in a row stop a stage. What is left waits for the next run.

## Running polish locally (Mac)

One-time: install and sign in.
```
curl -fsSL https://antigravity.google/cli/install.sh | bash     # installs ~/.local/bin/agy
agy                                                              # interactive, sign in once
```
Check the model list and that the pinned slug is in it:
```
agy models                           # or: tools/polish_local.sh --check-models
```
Smoke-test one headless call (also confirms the first-run workspace-trust prompt does not block headless mode):
```
cd "$(mktemp -d)" && agy -p "Reply with exactly: ok" --model gemini-3.8-flash-medium --output-format json
```
Polish:
```
tools/polish_local.sh --dry-run      # how many texts are pending (no calls)
tools/polish_local.sh --limit 6      # first small real run: polishes 6 texts, renders, verifies, commits locally
git show HEAD                        # review the before/after
tools/polish_local.sh                # everything pending (about 500 texts on the first run), commits locally
tools/polish_local.sh --push         # same, then pushes
```
The script needs a clean tree, runs `git pull --ff-only` on main, then `tools/i18n_pipeline.py --polish`, `render_readme.py`, `verify.py`, and
commits `data/` and the generated pages. `tools/local_daily.sh` (the local launchd update) now does translate + polish as part of the update when `agy` is installed.
Other commands: `python3 tools/i18n_pipeline.py --polish --targets projects,categories --limit 20`.
