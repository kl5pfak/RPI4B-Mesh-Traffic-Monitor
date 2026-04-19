# Changelog

All notable changes to this project are documented in this file.

This format is based on Keep a Changelog.

## [Unreleased]

### Added
- None yet.

### Changed
- None yet.

### Fixed
- None yet.

## [0.2.0-beta] - 2026-04-18

### Added
- Emergency alert beta pipeline for verified DeskQuake events.
- Mesh-only emergency alert broadcast path in gateway.
- Alerts queue file: data/alerts_queue.jsonl.
- Secondary monitor support for alert stream output.
- Gateway startup log line that shows mesh-only emergency alert mode.

### Changed
- README updated with emergency alert beta behavior and run flags.
- Repository housekeeping updated to ignore local .vscode folder.

## [0.1.0] - 2026-04-18

### Added
- Initial DeskQuake event pipeline components.
- Gateway intake and event queue writer.
- Verifier service with mock and optional API-backed verification.
- Monitor for event and verification streams.
- JSONL queue-based inter-process data flow.

[Unreleased]: https://github.com/kl5pfak/RPI4B-Mesh-Traffic-Monitor/compare/e31448f...HEAD
[0.2.0-beta]: https://github.com/kl5pfak/RPI4B-Mesh-Traffic-Monitor/compare/0.1.0...0.2.0-beta
[0.1.0]: https://github.com/kl5pfak/RPI4B-Mesh-Traffic-Monitor/releases/tag/0.1.0
