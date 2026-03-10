# Contributing Guide

Thanks for contributing to this project.
This guide keeps contributions consistent, reviewable, and safe.

## Code of Conduct

- Be respectful and constructive in discussions and reviews.
- Focus feedback on code and behavior, not people.
- Assume positive intent and ask clarifying questions when needed.

## Before You Start

1. Open an issue (or comment on an existing one) to discuss non-trivial changes.
2. Keep scope focused. Prefer small, incremental pull requests.
3. For UX/UI changes in bot messages, commands, keyboards, or flows, follow `.github/copilot-instructions.md`.

## Development Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies.

Example:

```bash
git clone https://github.com/artcc/send-torrent-telegram-bot.git
cd send-torrent-telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Configuration

1. Copy `.env.example` to `.env`.
2. Set required variables such as `TELEGRAM_BOT_TOKEN` and `ALLOWED_CHAT_IDS`.
3. Use a local `WATCH_FOLDER` for development testing.

## Branching and Commits

- Branch naming suggestions:
  - `feat/<short-description>`
  - `fix/<short-description>`
  - `docs/<short-description>`
  - `chore/<short-description>`
- Commit messages should be concise and imperative.

Examples:
- `feat(rss): add page counter in browse flow`
- `fix(messages): normalize error icon usage`
- `docs(readme): update persistent keyboard section`

## Coding Guidelines

- Keep changes minimal and targeted.
- Avoid unrelated refactors in the same PR.
- Preserve existing functionality unless the issue explicitly requires behavior changes.
- Prefer clear names and small functions.
- Add or update documentation when behavior, commands, or UX/UI change.

## UX/UI Rules for Telegram Flows

All UX/UI contributions must align with `.github/copilot-instructions.md`:

- Global navigation via persistent keyboard.
- Inline buttons only for contextual actions.
- Confirmation required for destructive actions.
- Consistent status icons: ℹ️ ✅ ⚠️ ❌.
- Error messages must be actionable and include a next step.

## Testing and Validation

Run checks before opening a pull request.

```bash
python3 -m compileall bot
```

If you use local lint/test tooling in your environment, run them too and include results in the PR description.

## Pull Request Checklist

- [ ] Scope is focused and related to a single objective.
- [ ] No unrelated files or formatting-only noise.
- [ ] Code compiles and local checks pass.
- [ ] Documentation is updated when needed.
- [ ] UX/UI changes follow `.github/copilot-instructions.md`.
- [ ] Screenshots or interaction notes included for user-facing changes.
- [ ] PR description explains what changed and why.

## Pull Request Template (Recommended)

Use this structure in your PR description:

```md
## Summary
- What changed
- Why it changed

## Scope
- In scope
- Out of scope

## Validation
- Commands run
- Results

## UX/UI Impact (if applicable)
- Commands affected
- Keyboard changes
- Inline flow changes
```

## Security Notes

- Never commit secrets (`.env`, tokens, API keys).
- Do not log sensitive values.
- Report security concerns privately to maintainers.

## Review Expectations

- Maintainers may request changes before merge.
- PRs should be mergeable, clear, and reproducible.
- Keep discussions on the PR thread for traceability.

Thanks again for contributing.
