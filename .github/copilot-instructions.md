# Telegram Bot UX/UI Guidelines

These are the global UX/UI rules for this project.
Any change in commands, messages, keyboards, or interaction flows must follow this document to keep a consistent interface.

## UX Goal

Build a Telegram bot that is clear, predictable, and fast to use from day one.
The user should always know:
- what happened,
- what can be done next,
- how to recover from errors.

## Mandatory Design Principles

1) Dual access for core actions
- Every main action must be available through:
  - a slash command,
  - a persistent keyboard button when applicable.

2) Consistent command naming
- Commands must be short, concrete, and predictable.
- Use the same verb style across all commands.
- Register commands via setMyCommands with one-line practical descriptions.

3) Persistent keyboard for global navigation
- Use ReplyKeyboardMarkup for always-available actions.
- Keep it compact: 2 to 4 main buttons.
- Avoid clutter and avoid low-value buttons.
- Re-show the keyboard after important actions.

4) Inline buttons only for context
- Use InlineKeyboardMarkup for local decisions within a flow:
  - select option,
  - confirm or cancel,
  - refresh list,
  - perform row-level action.
- Do not use inline buttons for global navigation.

5) Mandatory confirmation on destructive actions
- Any destructive or irreversible action requires inline confirmation.
- Always use a clear pair:
  - Confirm
  - Cancel

6) Unified message system
- All status messages must follow this icon convention:
  - ℹ️ info
  - ✅ success
  - ⚠️ warning
  - ❌ error
- Messages must be short, direct, and actionable.
- Avoid long blocks of text when a short summary plus next step is enough.

7) Consistent conversational tone
- Tone must be professional, calm, and concise.
- Never blame the user.
- On errors, explain what happened and what the user can do now.

8) Responsive interaction
- Show typing action when an operation may take noticeable time.
- For long operations, provide progress-friendly updates when possible.

9) Robustness in user flows
- Respect Telegram limits (message length, callback behavior, etc.).
- If a service fails, keep the flow alive with a helpful fallback message.
- Never leave the user without a clear next action.

## Interface Patterns

### A) Command and button parity
- If a feature appears in the persistent keyboard, it must have an equivalent slash command.
- If a feature is command-only for technical reasons, explain that reason in docs.

### B) Error message pattern
- Use this structure:
  - what failed,
  - likely cause (if known),
  - next step.

Example:
- ❌ Could not refresh subscriptions.
- Try again in a few seconds. If the issue persists, use /status.

### C) Empty states
- Every empty list or missing-data state must provide:
  - a clear explanation,
  - a direct action button or command suggestion.

### D) Confirmation copy
- Confirmation prompts must explicitly mention the target resource.
- Avoid generic prompts like "Are you sure?" without context.

## UX/UI Acceptance Checklist

- Commands are registered and descriptions are understandable.
- Persistent keyboard is present and compact.
- Inline buttons are contextual and not used as global menu.
- Destructive actions require Confirm/Cancel.
- ℹ️ ✅ ⚠️ ❌ iconography is applied consistently.
- Errors are friendly and actionable.
- User can always identify a next step after each response.

## Documentation Consistency Rule

Any UX/UI change must be reflected in project documentation:
- command list,
- persistent buttons,
- contextual inline flows,
- relevant examples of status/error messages.