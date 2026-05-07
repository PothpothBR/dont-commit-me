from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath

from dont_commit_me.config import Config, FileRule, LineRule, MisconfiguredRule, load_config

GRAY  = "\033[90m"
BOLD  = "\033[1m"
CYAN  = "\033[36;1m"
RED   = "\033[31;1m"
RESET = "\033[0m"


def get_staged_diff(cwd: str | None = None) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout.splitlines()


BLOCK_BREAK = None  # sentinel between @@ hunks

DiffEntry = tuple[str, int, str]  # (kind, line_num, content): kind = "+" or "-"

def parse_diff(lines: list[str]) -> dict[str, list[DiffEntry | None]]:
    files: dict[str, list[DiffEntry | None]] = {}
    current_file: str | None = None
    add_line = 0
    rem_line = 0
    first_hunk = True

    for line in lines:
        if line.startswith("+++ b/"):
            current_file = line[6:]
            files.setdefault(current_file, [])
            first_hunk = True
        elif line.startswith("--- "):
            pass
        elif line.startswith("@@ "):
            m_add = re.search(r"\+(\d+)", line)
            m_rem = re.search(r"-(\d+)", line)
            add_line = int(m_add.group(1)) if m_add else 0
            rem_line = int(m_rem.group(1)) if m_rem else 0
            if current_file is not None and not first_hunk:
                files[current_file].append(BLOCK_BREAK)
            first_hunk = False
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file is not None:
                files[current_file].append(("+", add_line, line[1:]))
            add_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            if current_file is not None:
                files[current_file].append(("-", rem_line, line[1:]))
            rem_line += 1
        else:
            add_line += 1
            rem_line += 1

    return files


class InvalidPattern(Exception):
    pass


def match_line_rule(rule: LineRule, line: str) -> tuple[bool, str | None]:
    """Returns (matched, matched_contains)"""
    if rule.start_with:
        stripped = line.lstrip()
        if not any(stripped.startswith(p) for p in rule.start_with):
            return False, None
    matched_contains = None
    if rule.contains:
        matched_contains = next((c for c in rule.contains if c in line), None)
        if not matched_contains:
            return False, None
    if rule.match:
        try:
            if not re.search(rule.match, line):
                return False, None
        except re.error as e:
            raise InvalidPattern(f"Invalid match pattern \"{rule.match}\": {e}") from e
    return True, matched_contains



def find_span(rule: LineRule | FileRule, line: str, matched_contains: str | None = None) -> tuple[int, int] | None:
    if rule.match:
        try:
            m = re.search(rule.match, line)
        except re.error as e:
            raise InvalidPattern(f"Invalid match pattern \"{rule.match}\": {e}") from e
        if m:
            return m.start(), m.end()
    target = matched_contains or (rule.contains[0] if rule.contains else None)
    if target:
        idx = line.find(target)
        if idx != -1:
            return idx, idx + len(target)
    return None


def diff_chars(old: str, new: str) -> str:
    """Highlight chars in new that differ from old, in blue bold."""
    import difflib
    matcher = difflib.SequenceMatcher(None, old, new)
    result = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        chunk = new[j1:j2]
        if op == "equal":
            result.append(f"{BOLD}{chunk}{RESET}")
        else:
            result.append(f"{CYAN}{chunk}{RESET}")
    return "".join(result)


def highlight_line(line: str, span: tuple[int, int] | None, old_line: str | None = None) -> str:
    if old_line is not None:
        return diff_chars(old_line, line.rstrip())
    if not span:
        return f"{BOLD}{line.rstrip()}{RESET}"
    s, e = span
    return (
        f"{BOLD}{line[:s]}"
        f"{CYAN}{line[s:e]}"
        f"{RESET}{BOLD}{line[e:].rstrip()}{RESET}"
    )


def line_rule_label(rule: LineRule, index: int, matched_contains: str | None = None) -> str:
    if rule.match:
        return f"Line Rule #{index} · Match \"{rule.match}\""
    if matched_contains:
        return f"Line Rule #{index} · Contains \"{matched_contains}\""
    if rule.contains:
        return f"Line Rule #{index} · Contains \"{rule.contains[0]}\""
    return f"Line Rule #{index}"


def file_rule_label(rule: FileRule, index: int, matched_path: str = "") -> str:
    path_str = f"\"{matched_path}\"" if matched_path else ""
    if rule.no_changes:
        return f"File Rule #{index} · No changes {path_str}"
    if rule.match:
        return f"File Rule #{index} · Match \"{rule.match}\""
    for c in rule.contains:
        return f"File Rule #{index} · Contains \"{c}\""
    return f"File Rule #{index}"


@dataclass
class Finding:
    filename: str
    rule_label: str
    lines: list[tuple[int, str, tuple[int, int] | None]]
    total: int = 0

    def __post_init__(self):
        if not self.total:
            self.total = len(self.lines)


def check_line_rules(
    diff_files: dict[str, list[tuple[int, str]]], config: Config
) -> list[Finding]:
    findings = []
    for filename, added_lines in diff_files.items():
        ext = Path(filename).suffix
        applicable = [(i + 1, r) for i, r in enumerate(config.line_rules) if ext in r.extensions]
        # group matches per (filename, rule)
        rule_hits: dict[tuple[str, int], tuple[LineRule, list]] = {}
        for entry in added_lines:
            if entry is None:
                continue
            kind, line_num, line_content = entry
            if kind != "+":
                continue
            for idx, rule in applicable:
                try:
                    matched, matched_contains = match_line_rule(rule, line_content)
                except InvalidPattern as e:
                    raise InvalidPattern(f"line_rule #{idx}: {e}") from e
                if matched:
                    key = (filename, idx)
                    if key not in rule_hits:
                        rule_hits[key] = (rule, [], matched_contains)
                    try:
                        span = find_span(rule, line_content, matched_contains)
                    except InvalidPattern as e:
                        raise InvalidPattern(f"line_rule #{idx}: {e}") from e
                    rule_hits[key][1].append((line_num, line_content, span, "line_rule"))
                    break
        for (fname, idx), (rule, lines, matched_contains) in rule_hits.items():
            findings.append(Finding(
                filename=fname,
                rule_label=line_rule_label(rule, idx, matched_contains),
                lines=lines,
                total=sum(1 for e in lines if e is not None and e[1].strip()),
            ))
    return findings


def check_file_rules(
    diff_files: dict[str, list[tuple[int, str]]], config: Config
) -> list[Finding]:
    findings = []
    for i, rule in enumerate(config.file_rules, start=1):
        for filename, added_lines in diff_files.items():
            path = PurePath(filename)
            matched_pattern = next((p for p in rule.paths if path.match(p)), None)
            if not matched_pattern:
                continue
            # pair removed lines with the next added line in same hunk
            removed_queue: list[str] = []
            real_lines = []
            pending_removed: dict[int, str] = {}  # add_line_num -> removed content
            rem_buf: list[str] = []

            for e in added_lines:
                if e is None:
                    # flush unpaired removed as red
                    for rc in rem_buf:
                        real_lines.append(("__rem__", rc, None, {}, "removed"))
                    rem_buf = []
                    real_lines.append(None)
                elif e[0] == "-":
                    rem_buf.append(e[2])
                else:
                    if rem_buf:
                        # pair: show as diff
                        old_line = rem_buf.pop(0)
                        real_lines.append((e[1], e[2], None, {old_line: old_line}, "paired"))
                    else:
                        real_lines.append((e[1], e[2], None, {}))

            # flush remaining unpaired removed
            for rc in rem_buf:
                real_lines.append(("__rem__", rc, None, {}, "removed"))
            if rule.no_changes:
                findings.append(Finding(
                    filename=filename,
                    rule_label=file_rule_label(rule, i, matched_pattern),
                    lines=real_lines,
                    total=sum(1 for e in real_lines if e is not None and e[1].strip()),
                ))
                continue
            matched_lines = []
            for entry in added_lines:
                if entry is None:
                    continue
                kind, line_num, line_content = entry
                if kind != "+":
                    continue
                try:
                    span = find_span(rule, line_content)
                except InvalidPattern as e:
                    raise InvalidPattern(f"file_rule #{i}: {e}") from e
                if span:
                    matched_lines.append((line_num, line_content, span, "file_rule"))
            if matched_lines:
                findings.append(Finding(
                    filename=filename,
                    rule_label=file_rule_label(rule, i, matched_pattern),
                    lines=matched_lines,
                    total=len(matched_lines),
                ))
    return findings


MAX_LINES = 5

def format_finding(f: Finding) -> str:
    out = [f"{GRAY}  {f.rule_label}{RESET}"]
    out.append(f"{GRAY}  {f.filename}{RESET}")
    shown_count = 0
    for entry in f.lines:
        if entry is None:
            if shown_count < MAX_LINES:
                out.append(f"{GRAY}  │ ...{RESET}")
            continue
        if len(entry) == 5:
            line_num, line_content, span, removed, kind = entry
        elif len(entry) == 4 and isinstance(entry[3], str):
            line_num, line_content, span, kind = entry
            removed = {}
        elif len(entry) == 4:
            line_num, line_content, span, removed = entry
            kind = "added"
        else:
            line_num, line_content, span = entry
            removed = {}
            kind = "added"
        if not isinstance(line_content, str) or not line_content.strip():
            continue
        if shown_count >= MAX_LINES:
            break
        if kind == "removed":
            out.append(f"{GRAY}  │{RESET} {RED}{BOLD}{line_content.rstrip()}{RESET}")
        elif kind == "paired":
            old_line = next(iter(removed.keys()), None)
            out.append(f"{GRAY}  │{RESET} {highlight_line(line_content, span, old_line)}")
        elif kind in ("line_rule", "file_rule"):
            out.append(f"{GRAY}  │{RESET} {highlight_line(line_content, span)}")
        else:
            out.append(f"{GRAY}  │{RESET} {CYAN}{BOLD}{line_content.rstrip()}{RESET}")
        shown_count += 1
    if f.total > MAX_LINES:
        skipped = f.total - MAX_LINES
        out.append(f"{GRAY}  │ ... +{skipped}{RESET}")
    return "\n".join(out)


def prompt_user() -> bool:
    tty_in = open("/dev/tty", "r")
    tty_out = open("/dev/tty", "w")
    try:
        while True:
            tty_out.write("\nContinue with commit anyway? [y/N] ")
            tty_out.flush()
            answer = tty_in.readline().strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no", ""):
                return False
            tty_out.write("Answer with 'y' or 'n'.\n")
            tty_out.flush()
    finally:
        tty_in.close()
        tty_out.close()


def main() -> int:
    if "--setup" in sys.argv:
        from dont_commit_me.wizard import run_wizard
        run_wizard()
        return 0

    try:
        config = load_config()
    except MisconfiguredRule as e:
        print(f"❌ Misconfiguration\n   {e}", file=sys.stderr)
        return 1

    if config is None:
        print("⚠️  Config not found. Run: dont-commit-me --setup", file=sys.stderr)
        return 1

    if not config.line_rules and not config.file_rules:
        with open("/dev/tty", "w") as tty:
            tty.write("\nNo rules configured. Run dont-commit-me --setup to get started.\n")
        return 0

    repo_dir = None
    if "--repo" in sys.argv:
        idx = sys.argv.index("--repo")
        if idx + 1 < len(sys.argv):
            repo_dir = sys.argv[idx + 1]

    diff_lines = get_staged_diff(cwd=repo_dir)
    diff_files = parse_diff(diff_lines)

    with open("/dev/tty", "w") as tty:
        tty.write("dont-commit-me\nLooking for unwanted changes...")
        tty.flush()

    try:
        findings = check_line_rules(diff_files, config) + check_file_rules(diff_files, config)
    except InvalidPattern as e:
        with open("/dev/tty", "w") as tty:
            tty.write(f"\n❌ Invalid regex in config: {e}\n")
        return 1

    if not findings:
        with open("/dev/tty", "w") as tty:
            tty.write(" Everything in place ✅ \n")
        return 0

    with open("/dev/tty", "w") as tty:
        tty.write(" ⚠️\n")

        if config.warnings:
            tty.write("\n")
            for w in config.warnings:
                tty.write(f"{w}\n")
        tty.write("\n")

        for f in findings:
            tty.write(format_finding(f))
            tty.write("\n\n")
        tty.flush()

    if config.stop_on_catch:
        with open("/dev/tty", "w") as tty:
            tty.write("❌ Commit blocked (stop_on_catch = true).\n")
        return 1

    if prompt_user():
        return 0

    with open("/dev/tty", "w") as tty:
        tty.write("❌ Commit aborted.\n")
    return 1

if __name__ == "__main__":
    sys.exit(main())