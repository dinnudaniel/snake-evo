#!/usr/bin/env python3
"""
Autonomous AI Agent powered by Claude Opus 4.6

This agent can autonomously:
  - Execute shell commands
  - Read and write files
  - Browse the web
  - List directory contents
  - Plan and complete multi-step tasks without human intervention

Usage:
    python agent.py "your task here"
    python agent.py   (interactive mode)
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.parse

import anthropic
from anthropic import beta_tool

# ── Client ────────────────────────────────────────────────────────────────────
client = anthropic.Anthropic()
MODEL = "claude-opus-4-6"
MAX_TURNS = 30  # safety limit

# ── Tool definitions ──────────────────────────────────────────────────────────

@beta_tool
def run_shell(command: str) -> str:
    """Run a shell command and return its combined stdout/stderr output.

    Use this to execute programs, run scripts, install packages,
    check processes, or perform any system-level operations.

    Args:
        command: The shell command string to execute.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd(),
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        combined = out
        if err:
            combined = f"{out}\n[stderr]: {err}" if out else f"[stderr]: {err}"
        if result.returncode != 0:
            combined = f"[exit {result.returncode}] {combined}"
        return combined or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 60 seconds"
    except Exception as exc:
        return f"Error: {exc}"


@beta_tool
def read_file(path: str) -> str:
    """Read and return the full contents of a file.

    Args:
        path: Absolute or relative path to the file.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except Exception as exc:
        return f"Error reading {path}: {exc}"


@beta_tool
def write_file(path: str, content: str) -> str:
    """Write (or overwrite) a file with the given content.

    Intermediate directories are created automatically.

    Args:
        path: Absolute or relative path to the file to write.
        content: The text content to write.
    """
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"Wrote {len(content)} characters to {path}"
    except Exception as exc:
        return f"Error writing {path}: {exc}"


@beta_tool
def append_file(path: str, content: str) -> str:
    """Append text to an existing file (or create it if it doesn't exist).

    Args:
        path: Path to the file.
        content: Text to append.
    """
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(content)
        return f"Appended {len(content)} characters to {path}"
    except Exception as exc:
        return f"Error appending to {path}: {exc}"


@beta_tool
def list_dir(path: str = ".") -> str:
    """List files and subdirectories at a given path.

    Args:
        path: Directory path to list. Defaults to the current directory.
    """
    try:
        entries = sorted(os.listdir(path))
        lines = []
        for name in entries:
            full = os.path.join(path, name)
            if os.path.isdir(full):
                lines.append(f"[dir]  {name}/")
            else:
                size = os.path.getsize(full)
                lines.append(f"[file] {name}  ({size:,} bytes)")
        return "\n".join(lines) if lines else "(empty)"
    except Exception as exc:
        return f"Error: {exc}"


@beta_tool
def web_fetch(url: str) -> str:
    """Fetch the raw text content of a web page or API endpoint.

    Returns up to 8 000 characters of the response body.

    Args:
        url: Full URL to fetch (must start with http:// or https://).
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (autonomous-agent/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        # Strip HTML tags simply so the text is more readable
        import re
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s{3,}", "\n\n", text).strip()
        return text[:8000] + (" …[truncated]" if len(text) > 8000 else "")
    except Exception as exc:
        return f"Error fetching {url}: {exc}"


@beta_tool
def web_search(query: str) -> str:
    """Search the web using the DuckDuckGo Instant Answer API and return
    a plain-text summary with related topics.

    Args:
        query: Natural-language search query.
    """
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (autonomous-agent/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        parts = []
        if data.get("AbstractText"):
            parts.append(f"Summary: {data['AbstractText']}")
        if data.get("Answer"):
            parts.append(f"Answer: {data['Answer']}")
        related = data.get("RelatedTopics", [])
        for item in related[:5]:
            if isinstance(item, dict) and item.get("Text"):
                parts.append(f"• {item['Text']}")
        if not parts:
            parts.append("No instant results. Try web_fetch with a specific URL.")
        return "\n".join(parts)
    except Exception as exc:
        return f"Search error: {exc}"


# ── Agentic loop ──────────────────────────────────────────────────────────────

TOOLS = [run_shell, read_file, write_file, append_file, list_dir, web_fetch, web_search]

SYSTEM_PROMPT = """You are an autonomous AI agent. Given a task, you will:
1. Break it into clear steps.
2. Use your tools to complete each step — do not ask the user for confirmation.
3. Verify results after each action and adjust if something goes wrong.
4. When the task is fully complete, write a short summary and stop.

Available tools:
- run_shell   — run any shell command
- read_file   — read a file
- write_file  — write / create a file
- append_file — append to a file
- list_dir    — list directory contents
- web_search  — DuckDuckGo search
- web_fetch   — fetch a URL

Always prefer concrete actions over lengthy explanations.
If a step fails, try an alternative approach. Never give up early.
"""


def run_agent(task: str) -> None:
    messages = [{"role": "user", "content": task}]
    print(f"\n{'='*60}")
    print(f"  TASK: {task}")
    print(f"{'='*60}\n")

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    turn = 0
    for message in runner:
        turn += 1
        if turn > MAX_TURNS:
            print("\n[Agent] Reached maximum turn limit.")
            break

        for block in message.content:
            if hasattr(block, "type"):
                if block.type == "thinking":
                    # Show condensed thinking
                    preview = block.thinking[:200].replace("\n", " ")
                    print(f"\n[thinking] {preview}{'...' if len(block.thinking) > 200 else ''}")
                elif block.type == "text" and block.text.strip():
                    print(f"\n[agent] {block.text.strip()}")
                elif block.type == "tool_use":
                    print(f"\n[tool:{block.name}] {json.dumps(block.input, ensure_ascii=False)[:120]}")
                elif block.type == "tool_result":
                    result_text = ""
                    if isinstance(block.content, list):
                        for c in block.content:
                            if hasattr(c, "text"):
                                result_text = c.text
                                break
                    elif isinstance(block.content, str):
                        result_text = block.content
                    preview = result_text[:200].replace("\n", " ")
                    print(f"  → {preview}{'...' if len(result_text) > 200 else ''}")

    print(f"\n{'='*60}")
    print("  AGENT FINISHED")
    print(f"{'='*60}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Export it before running:  export ANTHROPIC_API_KEY=your-key-here")
        sys.exit(1)

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        print("Autonomous AI Agent — powered by Claude Opus 4.6")
        print("Type your task and press Enter (or Ctrl+C to quit).\n")
        try:
            task = input("Task: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            sys.exit(0)

    if not task:
        print("No task provided. Exiting.")
        sys.exit(1)

    run_agent(task)


if __name__ == "__main__":
    main()
