# CHANGELOG.md

## 2026-10-29

- Rankings by stars/day (week, month, year) with total stars last, all from the GitHub API.
- Star history curve per project.
- READMEs in English, 简体中文, 繁體中文, 日本語, 한국어 with a language switcher.
- Daily update workflow and local script; removed unverifiable `stars_note` text.

## 2026-10-30

- Daily update at Beijing 00:00 and Los Angeles 00:00 (DST-aware).
- Every ranking shows the top 20; 22 projects tracked.
- Ranking history per time slot, `latest/`, and a history index linked from every README.
- New ranking: hottest new repos created in the last 7 days (search API, deduplicated against all other rankings).

## 2026-10-30 (i18n pipeline)

- All 39 untranslated new-repo descriptions translated into zh-Hans, zh-Hant, ja, ko (+ en for the 11 Chinese sources); every project blurb and category description already had all five languages (now enforced by a test).
- `tools/i18n_pipeline.py` + `tools/llm.py`: the scheduled update translates new descriptions into the cache (skipping anything already translated) in CI (Cursor CLI, optional `CURSOR_API_KEY` secret). Polish runs locally with the Antigravity CLI (`agy`, model `gemini-3.8-flash-medium`) via `tools/polish_local.sh` / `tools/local_daily.sh`. A failure keeps the existing text and never blocks the update.

## 2026-10-30 (translation library, slim README)

- `data/newcomer_i18n.json` became the translation library `data/translation_library.json`, keyed by repo + source-text hash + language. A hit costs no model call; only new or changed descriptions are translated, only missing languages are asked for; every run logs hits/new. Tests prove zero model calls on a full hit.
- `data/glossary.json`: fixed terms for common words; only the terms present in a batch go into the prompt. Polish sends only un-polished entries and logs how many were skipped.
- READMEs in all five languages are now a first screen: headline, one sentence, update stamp, the category leaders table (rows link to the category boards), then the category boards. Intro, schedule, "how it is produced", categories table and contributing moved to generated `docs/HOW_IT_WORKS*.md`; the long new-repo explanation moved there too.
- README first screen reworked (generator only): first line `GitHub 涨星榜 / GitHub Risers` (English: `GitHub Risers: Ranked by Stars Gained per Day`), header image `.github/social-preview.png`, three badges (MIT, CI, last updated), website link, three Q&A subheads linking `docs/FAQ.md`, a star prompt, a "how to cite" line (`CITATION.cff`) and a link to `docs/FACTS.md`. Each board shows the top 10 in the README; the full top 20 stays in `latest/`. Those linked files come from the GEO pull request (#9); the generator only links them, and a test checks the FAQ anchors.

## 2026-10-31 (ad-grade slogans)

- The 70 tracked projects now use the zh-Hans slogan set (pain first, only source facts; `tests/fixtures/slogans_zh.md`); zh-Hant / en / ja / ko were written to carry the same meaning and flavour. The 44 listed new repos were rewritten under the same rules (15 pre-activated installer labels and `t3dotgg/tstack` stay literal).
- The eight writing rules are part of `HOOK_RULE` / the hook prompt (`hooks.WRITING_RULES`). Previous hooks are kept as `hook_prev`; descriptions and translations are untouched.
- Accuracy pass: every hook (70 projects + 43 rewritten new repos) was checked against the repo's own GitHub description and README. 23 hooks that added a feature absent from the source or skewed the core purpose were rewritten in all five languages (e.g. grype no longer says "before it goes live", drawio no longer says "drag", openclaw no longer says data never leaves the machine, uncensored-ai-api now says it is uncensored); daisyui shortened. `hook_prev` and all descriptions/translations are unchanged; `tests/fixtures/slogans_zh.md` carries the new zh-Hans column and a revision note.

## 2026-10-30 (one-line hooks)

- Ranking tables show ONE short hook per project (`tools/hooks.py`: zh <= ~15 characters, en <= 60, ja/ko equally short) instead of the full description. Hooks are a separate field (`hook` in `data/projects.json` and inside each `data/translation_library.json` entry); every long description and translation is kept unchanged and listed on the new generated `docs/DETAILS*.md`.
- `tools/i18n_pipeline.py --hooks` stage (rule embedded in the prompt, length/hype/number guards); `tests/test_hooks.py` checks the limits per language and that every old entry survives (`tests/fixtures/pre_hook_baseline.json`).

## 2026-10-30 (categories)

- Rebranded to GitHub Risers with categories (AI first, then developer tools, security, web, infrastructure, design, data), each with new-repo, week, month, year and total boards.
- New-repo discovery is topic-only; suspected cracked/pirated repos are marked ⚠, ranked last and never shown as category leaders.

## 2026-10-30 (harness)

- Plan, backlog and governance files brought up to date; `python3 tools/next_plan.py --check`; harness regression tests. No change to rankings or generated pages.
