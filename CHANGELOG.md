# Changelog

All notable changes to this project are documented in this file.

The format is inspired by Keep a Changelog, and this project follows semantic versioning.

## [0.0.9] - 2026-03-10

### Changed
- Removed decorative dividers (━━━) and box-drawing characters from all bot messages.
- Unified message style across all handlers: consistent line breaks, no split phrases, no extra blank lines.
- Standardized message structure: title on first line, content always starts after a double newline.

## [0.0.8] - 2026-03-10

### Added
- Persistent global navigation keyboard (ReplyKeyboard) for core actions.
- Shared UX/UI guidelines for Telegram interactions in `.github/copilot-instructions.md`.
- `CONTRIBUTING.md` with contribution flow, validation checklist, and UX/UI contribution rules.
- README section documenting persistent keyboard actions.

### Changed
- Global navigation flow now prioritizes persistent keyboard and slash command parity.
- Global bot responses re-show the persistent keyboard after key interactions.
- RSS command responses were aligned to the same global UX rules while keeping contextual inline actions for selection/pagination/confirmation.
- README command descriptions updated to reflect keyboard-first global navigation.

### Fixed
- Consistency issues where global navigation previously depended on inline buttons.

## [0.0.7] - 2026-03-06

### Added
- Automatic cleanup for `.torrent` files in watch folder.
- Configurable cleanup delay via environment variable.

## [0.0.6] - 2026-02-04

### Added
- Global error handler for centralized exception logging and user-friendly fallback responses.

## [0.0.5] - 2026-01-12

### Added
- Multi-RSS support with per-user feed management.
- RSS pagination for browsing larger feeds.
- RSS delete flow with management actions.

### Changed
- UI and command set expanded with `/chatid` and `/author`.
- Bot text style and message structure refactoring.

## [0.0.4] - 2026-01-11

### Added
- RSS browsing and download flows refactored into dedicated handlers/modules.
- Pagination and cancel support in RSS selection interface.

### Fixed
- Message edit handling improvements in RSS callback flow.
- Loading message formatting improvements in RSS navigation.

## [0.0.3] - 2026-01-11

### Added
- Multi-selection of RSS items with visual toggle state.
- Batch RSS download action for selected torrents.

### Changed
- RSS browsing UI improved with clearer selection and download affordances.

## [0.0.2] - 2026-01-11

### Added
- Docker Compose usage examples and RSS persistence instructions in README.
- Environment variable documentation updates for RSS data paths.

### Changed
- Batch summary formatting for uploaded torrents.
- RSS browsing UX copy and structure improvements.

## [0.0.1] - 2026-01-10

### Added
- Initial public baseline for Send Torrent Telegram Bot.
- Core torrent upload flow: receive `.torrent` files and place them in watch folder.
- Authorization by allowed chat IDs.
- Dockerized deployment and CI/CD foundations.
- Initial README and bot identity updates.
