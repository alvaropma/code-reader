#!/usr/bin/env python3
"""code-reader — A TUI for browsing GitHub repositories."""

import os
import subprocess
import sys
from typing import Optional

from openai import OpenAI
from rich.markup import escape
from rich.syntax import Syntax
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from github_client import GitHubClient, RepoFile, RepoInfo


def _get_openai_client() -> Optional[OpenAI]:
    """Get an OpenAI-compatible client. Tries OPENAI_API_KEY first, then GitHub token."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAI(api_key=api_key)

    # Fall back to GitHub Models (OpenAI-compatible) via gh CLI token
    gh_token = _gh_cli_token()
    if gh_token:
        return OpenAI(
            api_key=gh_token,
            base_url="https://models.inference.ai.azure.com",
        )
    return None


def _gh_cli_token() -> Optional[str]:
    """Try to get token from gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ── File type detection ───────────────────────────────────────────────────────

LANGUAGE_MAP = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "tsx": "tsx",
    "jsx": "jsx",
    "rb": "ruby",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "kt": "kotlin",
    "swift": "swift",
    "c": "c",
    "cpp": "cpp",
    "h": "c",
    "hpp": "cpp",
    "cs": "csharp",
    "php": "php",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "fish": "fish",
    "ps1": "powershell",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "scss": "scss",
    "less": "less",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "xml": "xml",
    "md": "markdown",
    "rst": "rst",
    "tex": "latex",
    "r": "r",
    "lua": "lua",
    "vim": "vim",
    "dockerfile": "dockerfile",
    "tf": "terraform",
    "hcl": "terraform",
    "proto": "protobuf",
    "graphql": "graphql",
    "dart": "dart",
    "ex": "elixir",
    "exs": "elixir",
    "erl": "erlang",
    "hs": "haskell",
    "ml": "ocaml",
    "clj": "clojure",
    "scala": "scala",
    "zig": "zig",
    "nim": "nim",
    "vue": "vue",
    "svelte": "svelte",
}

ICON_MAP = {
    "dir": "📁",
    "py": "🐍",
    "js": "🟨",
    "ts": "🔷",
    "tsx": "🔷",
    "jsx": "🟨",
    "go": "🔵",
    "rs": "🦀",
    "rb": "💎",
    "java": "☕",
    "md": "📝",
    "json": "📋",
    "yaml": "📋",
    "yml": "📋",
    "toml": "📋",
    "html": "🌐",
    "css": "🎨",
    "sh": "🐚",
    "sql": "🗃️",
    "dockerfile": "🐳",
    "lock": "🔒",
}

# Files to skip in tree display
SKIP_PATTERNS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".DS_Store",
    "vendor",
    ".next",
    ".nuxt",
    "dist",
    "build",
    ".cache",
}


def get_icon(rf: RepoFile) -> str:
    if rf.is_dir:
        return ICON_MAP.get("dir", "📁")
    return ICON_MAP.get(rf.extension, "📄")


def get_language(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    # Special filenames
    lower = filename.lower()
    if lower == "dockerfile":
        return "dockerfile"
    if lower == "makefile":
        return "makefile"
    return LANGUAGE_MAP.get(ext, "text")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ── Widgets ───────────────────────────────────────────────────────────────────


class RepoOverview(Static):
    """Shows repository metadata."""

    def update_info(self, info: RepoInfo, languages: dict[str, int]) -> None:
        total = sum(languages.values()) or 1
        lang_bars: list[str] = []
        for lang, bytes_ in sorted(languages.items(), key=lambda x: -x[1])[:8]:
            pct = bytes_ / total * 100
            lang_bars.append(f"  [#818cf8]{lang}[/] [dim]{pct:.1f}%[/]")

        topics = (
            " ".join(f"[on #1e293b] {t} [/]" for t in info.topics[:6])
            if info.topics
            else "[dim]none[/]"
        )

        self.update(
            f"[bold #e2e8f0]{info.full_name}[/]\n"
            f"[#94a3b8]{info.description}[/]\n\n"
            f"[#fbbf24]★[/] {info.stars:,}  "
            f"[#6366f1]⑂[/] {info.forks:,}  "
            f"[#34d399]⊙[/] {info.open_issues} issues  "
            f"[dim]{format_size(info.size_kb * 1024)}[/]  "
            f"[dim]{info.license_name or 'No license'}[/]\n\n"
            f"[bold #5eead4]Languages[/]\n" + "\n".join(lang_bars) + "\n\n"
            f"[bold #5eead4]Topics[/]  {topics}"
        )


class FilePreview(VerticalScroll):
    """Right panel showing file content with syntax highlighting."""

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim italic]Select a file to preview[/]",
            id="file-content",
            markup=True,
        )

    def show_file(self, content: str, filename: str) -> None:
        widget = self.query_one("#file-content", Static)
        lang = get_language(filename)
        try:
            syntax = Syntax(
                content,
                lang,
                theme="dracula",
                line_numbers=True,
                word_wrap=False,
            )
            widget.update(syntax)
        except Exception:
            widget.update(content)
        self.scroll_home(animate=False)

    def show_message(self, msg: str) -> None:
        self.query_one("#file-content", Static).update(msg)

    def show_overview(self, info: RepoInfo, languages: dict[str, int]) -> None:
        total = sum(languages.values()) or 1
        lang_lines: list[str] = []
        for lang, bytes_ in sorted(languages.items(), key=lambda x: -x[1])[:10]:
            pct = bytes_ / total * 100
            bar_len = int(pct / 2)
            bar = "█" * bar_len + "░" * (50 - bar_len)
            lang_lines.append(
                f"  [#818cf8]{lang:15s}[/] [#334155]{bar}[/] [dim]{pct:5.1f}%[/]"
            )

        topics = (
            "  ".join(f"[on #1e1b4b] {t} [/]" for t in info.topics)
            if info.topics
            else "[dim]none[/]"
        )

        text = (
            f"[bold #5eead4]Repository Overview[/]\n"
            f"{'─' * 60}\n\n"
            f"[bold #e2e8f0]{info.full_name}[/]\n"
            f"[#94a3b8]{info.description}[/]\n\n"
            f"[#fbbf24]★ Stars[/]       {info.stars:,}\n"
            f"[#6366f1]⑂ Forks[/]       {info.forks:,}\n"
            f"[#34d399]⊙ Issues[/]      {info.open_issues}\n"
            f"[#f472b6]⊕ Size[/]        {format_size(info.size_kb * 1024)}\n"
            f"[#fb923c]⊗ License[/]     {info.license_name or 'None'}\n"
            f"[#22d3ee]⊘ Branch[/]      {info.default_branch}\n\n"
            f"[bold #5eead4]Language Breakdown[/]\n"
            f"{'─' * 60}\n" + "\n".join(lang_lines) + "\n\n"
            f"[bold #5eead4]Topics[/]\n"
            f"  {topics}"
        )
        self.query_one("#file-content", Static).update(text)
        self.scroll_home(animate=False)


class ChatPanel(Vertical):
    """LLM chat panel for asking questions about code."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._log_text: str = ""

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #5eead4]💬 Ask about this code[/]\n[dim]Type a question below[/]",
            id="chat-header",
        )
        with VerticalScroll(id="chat-messages"):
            yield Static("", id="chat-log")
        yield Input(
            placeholder="Ask about this file...",
            id="chat-input",
        )

    def append_message(self, role: str, content: str) -> None:
        if role == "user":
            new_line = f"\n[bold #818cf8]You:[/] {escape(content)}"
        else:
            new_line = f"\n[#94a3b8]{content}[/]"
        self._log_text = (self._log_text + new_line).strip()
        self.query_one("#chat-log", Static).update(self._log_text)
        self.query_one("#chat-messages", VerticalScroll).scroll_end(animate=False)

    def update_streaming(self, full_response: str) -> None:
        """Update the last assistant message during streaming."""
        marker = "\n[#94a3b8]"
        idx = self._log_text.rfind(marker)
        if idx >= 0:
            base = self._log_text[:idx]
        else:
            base = self._log_text
        self._log_text = f"{base}\n[#94a3b8]{escape(full_response)}[/]".strip()
        self.query_one("#chat-log", Static).update(self._log_text)
        self.query_one("#chat-messages", VerticalScroll).scroll_end(animate=False)

    def clear_chat(self) -> None:
        self._log_text = ""
        self.query_one("#chat-log", Static).update("")


# ── Main App ──────────────────────────────────────────────────────────────────


class CodeReaderApp(App):
    """Browse GitHub repositories in your terminal."""

    TITLE = "code-reader"
    SUB_TITLE = "github repo browser"

    CSS = """
    Screen {
        background: #0f172a;
    }

    Header {
        background: #1e293b;
        color: #e2e8f0;
        height: 1;
    }

    #repo-input-bar {
        dock: top;
        height: 3;
        padding: 0 1;
        background: #0f172a;
    }

    #repo-input {
        width: 100%;
        border: round #6366f1;
        background: #1e293b;
        color: #f8fafc;
    }

    #repo-input:focus {
        border: round #818cf8;
    }

    #main-content {
        layout: horizontal;
        height: 1fr;
    }

    #tree-panel {
        width: 2fr;
        min-width: 30;
        background: #0f172a;
        padding: 0 1;
    }

    #file-tree {
        height: 2fr;
        background: #0f172a;
        scrollbar-color: #334155;
        scrollbar-color-hover: #475569;
    }

    #file-tree > .tree--guides {
        color: #334155;
    }

    #file-tree > .tree--cursor {
        background: #1e1b4b;
        color: #e2e8f0;
    }

    #chat-panel {
        height: 1fr;
        min-height: 8;
        background: #0f172a;
        border-top: solid #334155;
        padding: 0 0;
    }

    #chat-header {
        height: 2;
        padding: 0 1;
        background: #1e293b;
    }

    #chat-messages {
        height: 1fr;
        background: #0f172a;
        padding: 0 1;
        scrollbar-color: #334155;
        scrollbar-color-hover: #475569;
    }

    #chat-log {
        width: 100%;
    }

    #chat-input {
        dock: bottom;
        margin: 0 0;
        border: round #6366f1;
        background: #1e293b;
        color: #f8fafc;
        height: 3;
    }

    #chat-input:focus {
        border: round #818cf8;
    }

    #divider {
        width: 1;
        background: #334155;
    }

    #preview-panel {
        width: 3fr;
        height: 1fr;
        background: #111827;
        padding: 1 1;
        scrollbar-color: #334155;
        scrollbar-color-hover: #475569;
    }

    #file-content {
        width: 100%;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: #1e293b;
        layout: horizontal;
        padding: 0 1;
    }

    #status-left {
        width: 1fr;
        color: #94a3b8;
    }

    #status-right {
        width: auto;
        color: #64748b;
    }

    #help-bar {
        dock: bottom;
        height: 1;
        background: #1e293b;
        color: #94a3b8;
        content-align: center middle;
        text-align: center;
    }

    Footer {
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("escape", "focus_input", "Back to input", show=False),
        Binding("ctrl+o", "show_overview", "Overview", show=True),
        Binding("ctrl+l", "focus_chat", "Chat", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._client: Optional[GitHubClient] = None
        self._owner: str = ""
        self._repo: str = ""
        self._repo_info: Optional[RepoInfo] = None
        self._languages: dict[str, int] = {}
        self._file_count: int = 0
        self._current_file_path: str = ""
        self._current_file_content: str = ""
        self._openai: Optional[OpenAI] = None
        self._chat_history: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="repo-input-bar"):
            yield Input(
                placeholder="Enter repository (e.g. torvalds/linux) and press Enter",
                id="repo-input",
            )
        with Horizontal(id="main-content"):
            with Vertical(id="tree-panel"):
                yield Tree("Repository", id="file-tree")
                yield ChatPanel(id="chat-panel")
            yield Static(id="divider")
            yield FilePreview(id="preview-panel")
        with Horizontal(id="status-bar"):
            yield Static("", id="status-left")
            yield Static("", id="status-right")
        yield Static(
            "[#6366f1]Enter[/] load repo  "
            "[#6366f1]↑↓[/] navigate  "
            "[#6366f1]Enter[/] open file  "
            "[#6366f1]Ctrl+O[/] overview  "
            "[#6366f1]Ctrl+L[/] chat  "
            "[#6366f1]Esc[/] quit",
            id="help-bar",
            markup=True,
        )

    def on_mount(self) -> None:
        try:
            self._client = GitHubClient()
        except ValueError as e:
            self.notify(str(e), severity="error", timeout=5)

        # Initialize OpenAI-compatible client
        self._openai = _get_openai_client()
        if not self._openai:
            self.query_one("#chat-panel", ChatPanel).append_message(
                "assistant", "⚠ Set OPENAI_API_KEY to enable chat"
            )

        tree = self.query_one("#file-tree", Tree)
        tree.show_root = False

        # If a repo was passed as CLI arg, load it
        if len(sys.argv) > 1:
            repo_arg = sys.argv[1]
            inp = self.query_one("#repo-input", Input)
            inp.value = repo_arg
            self._load_repo(repo_arg)
        else:
            self.query_one("#repo-input", Input).focus()

    @on(Input.Submitted, "#repo-input")
    def on_repo_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self._load_repo(event.value.strip())

    @work(thread=True)
    def _load_repo(self, repo_str: str) -> None:
        if not self._client:
            self.call_from_thread(
                self.notify, "GitHub token not configured", severity="error"
            )
            return

        if "/" not in repo_str:
            self.call_from_thread(
                self.notify, "Use format: owner/repo", severity="warning"
            )
            return

        owner, repo = repo_str.split("/", 1)
        self._owner = owner
        self._repo = repo

        self.call_from_thread(self._set_status, f"Loading {owner}/{repo}...", "")
        self.call_from_thread(
            self.query_one("#preview-panel", FilePreview).show_message,
            f"[dim]Loading [bold]{owner}/{repo}[/bold]...[/]",
        )

        try:
            # Fetch repo info and languages in parallel-ish
            info = self._client.get_repo_info(owner, repo)
            self._repo_info = info
            languages = self._client.get_languages(owner, repo)
            self._languages = languages

            # Fetch file tree
            files = self._client.list_files(owner, repo, max_depth=3)
            self._file_count = self._count_files(files)

            self.call_from_thread(self._populate_tree, files)
            self.call_from_thread(
                self.query_one("#preview-panel", FilePreview).show_overview,
                info,
                languages,
            )
            self.call_from_thread(
                self._set_status,
                f"[#5eead4]{info.full_name}[/]  [#fbbf24]★ {info.stars:,}[/]  [dim]{info.language or ''}[/]",
                f"[dim]{self._file_count} files[/]",
            )
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Error: {e}", severity="error", timeout=5
            )
            self.call_from_thread(
                self.query_one("#preview-panel", FilePreview).show_message,
                f"[red]Error loading repository: {e}[/]",
            )

    def _count_files(self, files: list[RepoFile]) -> int:
        count = 0
        for f in files:
            if f.is_dir:
                count += self._count_files(f.children)
            else:
                count += 1
        return count

    def _populate_tree(self, files: list[RepoFile]) -> None:
        tree = self.query_one("#file-tree", Tree)
        tree.clear()
        tree.root.label = f"📦 {self._owner}/{self._repo}"
        tree.show_root = True
        self._add_files_to_tree(tree.root, files)
        tree.root.expand()

    def _add_files_to_tree(self, node: TreeNode, files: list[RepoFile]) -> None:
        for rf in files:
            if rf.name in SKIP_PATTERNS:
                continue
            icon = get_icon(rf)
            label = f"{icon} {rf.name}"
            if rf.is_dir:
                branch = node.add(label, data=rf)
                self._add_files_to_tree(branch, rf.children)
            else:
                size_str = format_size(rf.size) if rf.size else ""
                display = f"{label} [dim]{size_str}[/]" if size_str else label
                node.add_leaf(display, data=rf)

    @on(Tree.NodeSelected, "#file-tree")
    def on_tree_select(self, event: Tree.NodeSelected) -> None:
        rf = event.node.data
        if rf is None or rf.is_dir:
            return
        self._load_file(rf)

    @work(thread=True, exclusive=True)
    def _load_file(self, rf: RepoFile) -> None:
        if not self._client:
            return
        self.call_from_thread(
            self.query_one("#preview-panel", FilePreview).show_message,
            f"[dim]Loading {rf.path}...[/]",
        )
        try:
            content = self._client.read_file(self._owner, self._repo, rf.path)
            self._current_file_path = rf.path
            self._current_file_content = content
            self.call_from_thread(
                self.query_one("#preview-panel", FilePreview).show_file,
                content,
                rf.name,
            )
            self.call_from_thread(
                self._set_status,
                f"[#5eead4]{rf.path}[/]  [dim]{format_size(rf.size)}[/]  [dim]{get_language(rf.name)}[/]",
                f"[dim]{len(content.splitlines())} lines[/]",
            )
        except Exception as e:
            self.call_from_thread(
                self.query_one("#preview-panel", FilePreview).show_message,
                f"[red]Error reading file: {e}[/]",
            )

    def _set_status(self, left: str, right: str) -> None:
        self.query_one("#status-left", Static).update(left)
        self.query_one("#status-right", Static).update(right)

    def action_focus_input(self) -> None:
        inp = self.query_one("#repo-input", Input)
        if inp.has_focus:
            self.exit()
        else:
            inp.focus()

    def action_show_overview(self) -> None:
        if self._repo_info:
            self.query_one("#preview-panel", FilePreview).show_overview(
                self._repo_info, self._languages
            )

    def action_focus_chat(self) -> None:
        self.query_one("#chat-input", Input).focus()

    @on(Input.Submitted, "#chat-input")
    def on_chat_submitted(self, event: Input.Submitted) -> None:
        question = event.value.strip()
        if not question:
            return
        event.input.value = ""

        if not self._openai:
            self.query_one("#chat-panel", ChatPanel).append_message(
                "assistant", "⚠ OPENAI_API_KEY not set"
            )
            return

        chat = self.query_one("#chat-panel", ChatPanel)
        chat.append_message("user", question)
        chat.append_message("assistant", "thinking...")

        self._chat_history.append({"role": "user", "content": question})
        self._stream_response(question)

    @work(thread=True, exclusive=True, group="chat")
    def _stream_response(self, question: str) -> None:
        """Stream an OpenAI response in a background thread."""
        system_msg = "You are a helpful code assistant. Answer concisely about the code shown. Use markdown formatting sparingly — keep answers short (2-5 sentences typically)."

        if self._current_file_content:
            context = (
                f"The user is viewing `{self._current_file_path}` in repo "
                f"`{self._owner}/{self._repo}`.\n\n"
                f"File content:\n```\n{self._current_file_content[:12000]}\n```"
            )
        else:
            context = (
                f"The user is browsing repo `{self._owner}/{self._repo}`. "
                "No specific file is selected."
            )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "system", "content": context},
        ]
        # Include last few exchanges for continuity
        messages.extend(self._chat_history[-6:])

        try:
            stream = self._openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
                max_tokens=500,
            )
            full_response = ""
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_response += delta.content
                    self.call_from_thread(
                        self.query_one("#chat-panel", ChatPanel).update_streaming,
                        full_response,
                    )

            self._chat_history.append({"role": "assistant", "content": full_response})
        except Exception as e:
            self.call_from_thread(
                self.query_one("#chat-panel", ChatPanel).update_streaming,
                f"Error: {e}",
            )


def main() -> None:
    app = CodeReaderApp()
    app.run()


if __name__ == "__main__":
    main()
