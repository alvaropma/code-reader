# code-reader

A TUI for browsing GitHub repositories in your terminal. File tree, syntax-highlighted preview, and repository overview.

Built with Python + [Textual](https://textual.textualize.io/).

## Features

- **Browse any GitHub repo** — file tree with icons, sorted directories-first
- **Syntax highlighting** — Dracula theme, line numbers, 50+ languages supported
- **Repository overview** — stars, forks, language breakdown with visual bars, topics
- **All file types** — not just Python, everything from Rust to YAML
- **Auto-authentication** — uses `gh` CLI token, `GITHUB_TOKEN` env var, or `.env` file

## Install

Requires [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/alvaropma/code-reader.git
cd code-reader
uv sync
```

## Usage

```bash
# Interactive — type a repo name
uv run python app.py

# Direct — pass repo as argument
uv run python app.py torvalds/linux
```

## Keybindings

| Key | Action |
|---|---|
| Enter | Load repo / open file |
| ↑↓ | Navigate file tree |
| Ctrl+O | Show repo overview |
| Esc | Back to input / quit |
