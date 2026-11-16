# Changelog

All notable changes to git-explained. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-16

### Added
- Fonts ship with the plugin (Instrument Sans and Newsreader, SIL OFL 1.1), so reports work fully offline and make no network requests.
- Automated tests (`tests/`, standard library only) run on GitHub Actions for Python 3.8 to 3.13 on Linux, macOS and Windows.
- Demo GIF in the README.
- CONTRIBUTING.md, issue templates and this changelog.

### Fixed
- Reports, digests and scores are always read and written as UTF-8, so accents and emoji no longer break on Windows.
- Command output no longer fails on Windows consoles that use a legacy code page.

## [1.0.0] - 2026-11-15

### Added
- Packaged as a Claude Code plugin, with its own marketplace (`/plugin marketplace add mbaudran/git-explained`).
- Pull request mode: PR descriptions written from the push report, then linked back in the report.
- Weekly digests (HTML and Markdown to paste) for standups, managers and teams.
- English, French and Spanish.
- `--open` works on macOS, Linux and Windows.

### Fixed
- Two reports made in the same minute no longer overwrite each other.

[1.1.0]: https://github.com/mbaudran/git-explained/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mbaudran/git-explained/releases/tag/v1.0.0
