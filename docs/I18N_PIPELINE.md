# i18n pipeline: translate new repos, polish copy

Runs inside `python3 tools/update_stars.py --slot ...` (so in the daily workflow and in `tools/local_daily.sh`),
after the ranking is discovered and before the READMEs are rendered. Skip it with `--no-i18n`.

```
discover new repos ─▶ 1 translate (only what is missing) ─▶ 2 polish (only what is not polished yet) ─▶ render
```

Everything here is **fail-safe**: no key, no CLI, model not offered, a failed call, a reply that breaks a guard — the
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

## Model and key

- Model: `POLISH_MODEL` (repository variable or env), default **`gemini-3.8-flash-medium`** (Cursor's effort variants of
  Gemini 3.8 Flash are `-low`, `-medium`, `-high`). Translation uses the same model unless `I18N_TRANSLATE_MODEL` is set.
- Before use, `agent --list-models` must list that exact id. If it does not, the stage is skipped and the log names the
  models that are available. **No other model is ever substituted.**
- Key: environment variable `CURSOR_API_KEY`, in CI the repository secret of the same name (`${{ secrets.CURSOR_API_KEY }}`).
  It is never written to a file or a command line, never printed, and `GITHUB_TOKEN` is removed from the CLI's environment.
  Cursor bills third-party models such as Gemini from the account's credit (see the Cursor pricing docs).
- Every call is `agent -p --mode ask --trust --workspace <empty temp dir> --model <id>`: read-only, and the agent cannot see the repo.
- Limits: `I18N_BUDGET_SEC` (default 900) caps the time per run; 3 failed calls in a row stop a stage. What is left waits for the next run.

## Manual use

```
python3 tools/i18n_pipeline.py --dry-run                       # count the work, call nothing
CURSOR_API_KEY=... python3 tools/i18n_pipeline.py              # translate + polish now
CURSOR_API_KEY=... python3 tools/i18n_pipeline.py --polish --targets projects,categories --limit 20
python3 tools/render_readme.py                                  # then re-render
```
