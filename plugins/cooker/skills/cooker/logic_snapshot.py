#!/usr/bin/env python3
"""Logic snapshot/diff tool. Catches behavior drift when merging separately built parts.
Formatting and style differences are ignored.

Usage:
  python logic_snapshot.py snapshot <path> [<path> ...] -o snap.json   # BEFORE merging
  python logic_snapshot.py diff <before.json> <path_or_json>           # AFTER merging
"""
import argparse
import ast
import json
import os
import re
import sys
import textwrap

SKIP_DIRS = (".git", "node_modules", "__pycache__", "venv", ".venv")
JS_EXT = (".js", ".ts", ".jsx", ".tsx")
HTML_EXT = (".html", ".htm")
MODULE_CODE_KEY = "<module code>"  # virtual symbol holding top-level wiring
SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
# TypeScript writes `const X: SomeType = ...`; without allowing the annotation we lose constants.
JS_CONST_RE = re.compile(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::[^=\n]+)?=", re.MULTILINE)
# Type contracts are logic too - if they change during a merge we want to know.
TS_BLOCK_RE = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:interface|enum)\s+(\w+)", re.MULTILINE)
TS_ALIAS_RE = re.compile(r"^(?:export\s+)?type\s+(\w+)[^=\n]*=", re.MULTILINE)
# Named `export default` is already covered by JS_DEF_RE; match only anonymous ones here.
JS_DEFAULT_RE = re.compile(
    r"^export\s+default\s+(?:async\s+)?(?:function\s*\([^)]*\)\s*|\([^)]*\)\s*=>\s*)\{",
    re.MULTILINE,
)
JS_DEF_RE = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:function|class)\s+(\w+)"
    r"|^(?:export\s+)?const\s+(\w+)\s*=\s*(?:\(|async|\bfunction\b)",
    re.MULTILINE,
)

# Scan stats - so the tool never reports "all clear" when it actually read nothing.
LAST_SCAN = {"files_seen": 0, "files_read": 0, "parse_failures": []}


def reset_scan_stats():
    LAST_SCAN["files_seen"] = 0
    LAST_SCAN["files_read"] = 0
    LAST_SCAN["parse_failures"] = []


def _walk_files(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in files:
            yield os.path.join(dirpath, f)


def _extract_python(path, text):
    out = {}
    try:
        tree = ast.parse(text)
    except SyntaxError as err:
        LAST_SCAN["parse_failures"].append(f"{path}: {err}")
        return out

    lines = text.splitlines(keepends=True)

    def segment(node):
        # get_source_segment drops decorators. Losing @cache is a behavior change, so include them.
        start = node.lineno
        if getattr(node, "decorator_list", None):
            start = min(d.lineno for d in node.decorator_list)
        return "".join(lines[start - 1:node.end_lineno])

    def visit(body, prefix):
        # Methods are keyed as A.run / B.run - otherwise same-named methods overwrite each other.
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                out[name] = segment(node)
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + ".")

    visit(tree.body, "")

    # Top-level executable code (init calls, wiring). Merges quietly change this.
    wiring = [
        node for node in tree.body
        if not isinstance(node, (
            ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
            ast.Assign, ast.AnnAssign, ast.Import, ast.ImportFrom,
        ))
    ]
    wiring_src = "\n".join(filter(None, (ast.get_source_segment(text, n) for n in wiring)))
    if wiring_src.strip():
        out[MODULE_CODE_KEY] = wiring_src

    # Module-level constants - logic living outside functions also disappears during merges.
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        seg = ast.get_source_segment(text, node) if targets else None
        for name in targets:
            if seg and name not in out:
                out[name] = seg
    return out


def _find_body_brace(text, from_index):
    """Locate the opening brace of a function body.

    Mistaking a destructured parameter (`function f({ a })`) for the body truncates the
    function and hides every change inside it, so parameter parens are skipped first.
    """
    i = from_index
    while i < len(text):
        ch = text[i]
        if ch == "(":
            close = _match_bracket(text, i)
            if close == -1:
                return -1
            i = close + 1
            continue
        if ch == "{":
            return i
        if ch == ";":
            return -1  # declaration without a body
        i += 1
    return -1


def _match_bracket(text, start):
    """Index of the bracket matching the opener at `start`. Brackets inside strings/comments
    are not counted."""
    opener = text[start]
    closer = {"{": "}", "[": "]", "(": ")"}[opener]
    depth = 0
    for m in TOKEN_RE.finditer(text, start):
        token = m.group(0)
        if token == opener:
            depth += 1
        elif token == closer:
            depth -= 1
            if depth == 0:
                return m.start()
    return -1


def _extract_js_constants(text):
    """Top-level const/let/var values. Function-shaped ones are handled by _extract_js."""
    out = {}
    for m in JS_CONST_RE.finditer(text):
        name = m.group(1)
        i = m.end()
        while i < len(text) and text[i] in " \t":
            i += 1
        if i < len(text) and text[i] in "{[":
            matched = _match_bracket(text, i)
            end = matched if matched != -1 else len(text) - 1
            end = text.find(";", end)
            end = len(text) - 1 if end == -1 else end
        else:
            end = text.find("\n", i)
            end = len(text) - 1 if end == -1 else end
        out[name] = text[m.start():end + 1]
    return out


def _extract_ts_types(text):
    """interface / enum / type aliases. A changed contract is a changed behavior."""
    out = {}
    for m in TS_BLOCK_RE.finditer(text):
        brace_start = text.find("{", m.end())
        if brace_start == -1:
            continue
        end = _match_bracket(text, brace_start)
        if end != -1:
            out[m.group(1)] = text[m.start():end + 1]
    for m in TS_ALIAS_RE.finditer(text):
        i = m.end()
        while i < len(text) and text[i] in " \t":
            i += 1
        if i < len(text) and text[i] == "{":
            matched = _match_bracket(text, i)
            end = matched if matched != -1 else i
        else:
            end = i
        semicolon = text.find(";", end)
        newline = text.find("\n", end)
        end = semicolon if semicolon != -1 and (newline == -1 or semicolon < newline) else newline
        if end == -1:
            end = len(text) - 1
        out[m.group(1)] = text[m.start():end + 1]
    return out


def _extract_js(text):
    # Pattern matching plus brace counting, not a real parser.
    # Upgrade path: swap in a JS/TS AST parser (esprima and friends).
    out = {}

    def put(name, body):
        # Same name declared twice in one file: keep both instead of overwriting.
        key = name
        n = 2
        while key in out:
            key = f"{name}#{n}"
            n += 1
        out[key] = body

    for m in JS_DEF_RE.finditer(text):
        name = m.group(1) or m.group(2)
        brace_start = _find_body_brace(text, m.start())
        if brace_start == -1:
            continue
        end = _match_bracket(text, brace_start)
        if end == -1:
            continue  # better to skip than to keep half a body
        put(name, text[m.start():end + 1])

    # export default function () {...} / export default () => {...}
    for m in JS_DEFAULT_RE.finditer(text):
        brace_start = text.find("{", m.end() - 1)
        if brace_start == -1:
            continue
        end = _match_bracket(text, brace_start)
        if end != -1:
            put("default", text[m.start():end + 1])
    return out


def _js_module_code(source, bodies):
    """Top-level code left over after declarations: listener hookups, init calls, wiring."""
    mask = bytearray(len(source))
    for body in bodies:
        start = source.find(body)
        if start == -1:
            continue
        for i in range(start, start + len(body)):
            mask[i] = 1
    remainder = "".join(ch for ch, hidden in zip(source, mask) if not hidden)
    lines = []
    for line in remainder.splitlines():
        stripped = line.strip()
        # import/export lines and stray punctuation are not wiring - merging always changes them.
        if not stripped or stripped in (";", "}", ")", "};", ");"):
            continue
        if re.match(r"^(import|export)\b", stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def snapshot(root):
    """returns {"relpath::name": source_text}"""
    result = {}
    for path in _walk_files(root):
        LAST_SCAN["files_seen"] += 1
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".py",) + JS_EXT + HTML_EXT:
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError as err:
            LAST_SCAN["parse_failures"].append(f"{path}: {err}")
            continue
        LAST_SCAN["files_read"] += 1
        if os.path.isfile(root):
            rel = os.path.basename(path)
        else:
            rel = os.path.relpath(path, root).replace("\\", "/")
        if ext == ".py":
            funcs = _extract_python(path, text)
        else:
            source = "\n".join(SCRIPT_RE.findall(text)) if ext in HTML_EXT else text
            funcs = _extract_js_constants(source)
            funcs.update(_extract_ts_types(source))
            funcs.update(_extract_js(source))  # function/class declarations win
            wiring = _js_module_code(source, funcs.values())
            if wiring.strip():
                funcs[MODULE_CODE_KEY] = wiring
        for name, src in funcs.items():
            result[f"{rel}::{name}"] = src
    return result


# String literals must be consumed before comments, or the // inside "https://..." reads as a
# comment. Comment syntax is language specific: // is floor division in Python, and # is an
# ordinary character inside a JS regex (/^#[0-9a-f]{6}$/). Mixing them truncates bodies.
_STRING_PART = (
    r'"""[\s\S]*?"""'
    r"|'''[\s\S]*?'''"
    r'|"(?:\\.|[^"\\\n])*"'
    r"|'(?:\\.|[^'\\\n])*'"
    r"|`(?:\\.|[^`\\])*`"
)
_TAIL_PART = r"|\w+|[^\s\w]"

JS_TOKEN_RE = re.compile(_STRING_PART + r"|//[^\n]*" + _TAIL_PART)
PY_TOKEN_RE = re.compile(_STRING_PART + r"|#[^\n]*" + _TAIL_PART)
TOKEN_RE = JS_TOKEN_RE  # _match_bracket is only used on the JS path


def _normalize(src, python=False):
    """Strip formatting, whitespace and comments; keep the logic tokens.
    A string literal becomes one token (quote style normalized).
    With python=True only # starts a comment, so // stays a floor-division operator.
    """
    tokens = []
    for match in (PY_TOKEN_RE if python else JS_TOKEN_RE).finditer(src):
        token = match.group(0)
        if token.startswith("#" if python else "//"):
            continue
        if token[:1] in "\"'`":
            if token[:3] in ('"""', "'''"):
                body = token[3:-3]
            else:
                body = token[1:-1]
            tokens.append('"' + body + '"')  # quote style is not logic
            continue
        tokens.append(token)
    return tokens


DECL_KEYWORDS = {"function", "const", "let", "var", "class", "def", "async", "export", "default"}


def _python_canonical(src):
    """Python only: canonical form with locals/parameters renamed in declaration order.
    Keeps a pure rename (`counts` -> `result`) from looking like a behavior change.
    Global, attribute and call names are contracts, so they are left alone.
    Returns None when the snippet does not parse.
    """
    try:
        tree = ast.parse(textwrap.dedent(src))
    except (SyntaxError, ValueError):
        return None

    mapping = {}

    def bind(name):
        if name not in mapping:
            mapping[name] = f"_v{len(mapping)}"
        return mapping[name]

    # Bind in declaration order. Using body order would make functions with swapped
    # parameters look identical.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
                bind(arg.arg)
            for extra in (args.vararg, args.kwarg):
                if extra:
                    bind(extra.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bind(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name)

    class Renamer(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in mapping:
                node.id = mapping[node.id]
            return node

        def visit_arg(self, node):
            if node.arg in mapping:
                node.arg = mapping[node.arg]
            return node

        def visit_ExceptHandler(self, node):
            self.generic_visit(node)
            if node.name in mapping:
                node.name = mapping[node.name]
            return node

    return ast.dump(Renamer().visit(tree))


def _normalize_anon(src, python=False):
    """Normalize with the declared name dropped, so renamed-and-moved logic still matches."""
    tokens = _normalize(src, python)
    i = 0
    while i < len(tokens) and tokens[i] in DECL_KEYWORDS:
        i += 1
    if i < len(tokens):
        return tokens[:i] + tokens[i + 1:]
    return tokens


MIN_RENAME_TOKENS = 10


def _rename_key(src, python=False):
    """Key used to follow a symbol that was only renamed. Very short bodies are excluded
    because they collide by accident.
    The 10-token threshold is a guess; raise it if short renamed helpers slip through.
    """
    tokens = _normalize_anon(src, python)
    return tuple(tokens) if len(tokens) >= MIN_RENAME_TOKENS else None


def diff_snapshots(before, after):
    """returns (changed, removed)

    changed: symbols whose logic differs. removed: symbols that vanished in the merge.
    Merging usually rearranges files (three parts into one), so when the path no longer
    matches we look the symbol up by name, and then by body.
    """
    def is_python(key):
        return key.split("::")[0].endswith(".py")

    def same_logic(a, b, python):
        """Whether two bodies are the same logic: AST with normalized names for Python,
        token comparison otherwise."""
        if python:
            canon_a = _python_canonical(a)
            if canon_a is not None:
                canon_b = _python_canonical(b)
                if canon_b is not None:
                    return canon_a == canon_b
        return _normalize(a, python) == _normalize(b, python)

    after_by_name = {}
    after_by_body = {}
    for key, src in after.items():
        after_by_name.setdefault(key.split("::")[-1], []).append(src)
        body_key = _rename_key(src, is_python(key))
        if body_key:
            after_by_body.setdefault(body_key, []).append(key)

    before_names = {k.split("::")[-1] for k in before}

    def survived_as_rename(before_src, key, python):
        """Whether the original logic survived under a different name.
        Only accepted when the candidate is unique - otherwise a codebase full of
        identical little helpers would hide real changes.
        """
        body = _rename_key(before_src, python)
        if not body:
            return False
        candidates = after_by_body.get(body)
        if not candidates or len(candidates) != 1:
            return False
        candidate_name = candidates[0].split("::")[-1]
        if candidate_name != key.split("::")[-1] and candidate_name in before_names:
            return False  # that name already existed before, so this is not a rename
        return True

    changed = []
    removed = []
    for key, before_src in before.items():
        python = is_python(key)
        if key in after:
            candidate = after[key]
        else:
            candidates = after_by_name.get(key.split("::")[-1])
            if not candidates:
                if survived_as_rename(before_src, key, python):
                    continue
                removed.append(key)
                continue
            if any(same_logic(before_src, c, python) for c in candidates):
                continue
            candidate = candidates[0]
        if not same_logic(before_src, candidate, python):
            if survived_as_rename(before_src, key, python):
                continue
            changed.append((key, before_src, candidate))

    # Wiring always changes when files are combined - keep it out of the change list.
    changed = [item for item in changed if not item[0].endswith(MODULE_CODE_KEY)]
    removed = [key for key in removed if not key.endswith(MODULE_CODE_KEY)]

    # If a method was reported, drop its parent class to avoid duplicate output.
    changed_keys = {k for k, _, _ in changed}
    all_keys = changed_keys | set(removed)

    def has_reported_child(key):
        return any(other.startswith(key + ".") for other in all_keys)

    changed = [item for item in changed if not has_reported_child(item[0])]
    removed = [key for key in removed if not has_reported_child(key)]
    return changed, removed


MAX_BODY_LINES = 24
MAX_DETAIL = 20  # with many changes, print bodies for the first few and names for the rest


def _clip(src):
    """Clip long bodies so one large class cannot eat the screen.
    Every line gets a `|` prefix so markdown or HTML inside a body cannot be confused
    with the report's own section headings.
    """
    lines = src.splitlines()
    if len(lines) > MAX_BODY_LINES:
        head = lines[:MAX_BODY_LINES - 6]
        tail = lines[-4:]
        omitted = len(lines) - len(head) - len(tail)
        lines = head + [f"... ({omitted} lines omitted, see the file) ..."] + tail
    return "\n".join("  | " + line for line in lines)


def _load_snapshot_json(path, label):
    """Read a snapshot file, reporting common mistakes in plain words instead of a traceback."""
    if os.path.isdir(path):
        print(f"!! {label} is a directory: {path}")
        print("   Arguments look swapped. Usage: diff <before.json> <merged_path>")
        sys.exit(2)
    if not os.path.exists(path):
        print(f"!! {label} not found: {path}")
        print("   Did you run the snapshot command before merging?")
        sys.exit(2)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        print(f"!! {label} is not valid JSON: {path}")
        print(f"   {err}")
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"!! {label} has the wrong shape (not an object): {path}")
        sys.exit(2)
    return data


def _report_scan_problems(symbol_count):
    seen = LAST_SCAN["files_seen"]
    read = LAST_SCAN["files_read"]
    failures = LAST_SCAN["parse_failures"]
    if failures:
        print(f"\n!! {len(failures)} file(s) could not be read - they were NOT checked:")
        for item in failures[:10]:
            print(f"  - {item}")
    if seen and read == 0:
        print(f"\n!! Warning: saw {seen} file(s) but none in a supported language "
              "(.py .js .ts .jsx .tsx .html).")
        print("   This tool cannot check them. Do not report the merge as verified.")
    elif symbol_count == 0 and read:
        print(f"\n!! Warning: read {read} file(s) but found no trackable symbols.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="record the parts before merging")
    p_snap.add_argument("roots", nargs="+", help="one or more files/directories, merged into one snapshot")
    p_snap.add_argument("-o", "--out", required=True)

    p_diff = sub.add_parser("diff", help="compare a snapshot against the merged result")
    p_diff.add_argument("before_json")
    p_diff.add_argument("after_root_or_json")

    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.cmd == "snapshot":
        missing = [r for r in args.roots if not os.path.exists(r)]
        if missing:
            print("!! Path not found (typo, or not created yet):")
            for item in missing:
                print(f"  - {item}")
            sys.exit(2)
        reset_scan_stats()
        snap = {}
        for root in args.roots:
            snap.update(snapshot(root))
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        print(f"[snapshot saved: {args.out}, {len(snap)} symbols]")
        _report_scan_problems(len(snap))
        return sys.exit(2) if len(snap) == 0 else None

    if args.cmd == "diff":
        reset_scan_stats()
        before = _load_snapshot_json(args.before_json, "before-snapshot")
        target = args.after_root_or_json
        if target.endswith(".json"):
            after = _load_snapshot_json(target, "merged snapshot")
        elif not os.path.exists(target):
            print(f"!! Merged path not found: {target}")
            sys.exit(2)
        else:
            after = snapshot(target)

        # Never let the tool say "all clear" when it read nothing.
        if not before:
            print("!! Cannot check: the before-snapshot has 0 symbols. This is NOT an all-clear.")
            _report_scan_problems(0)
            sys.exit(2)
        if not after:
            print("!! Cannot check: no symbols found in the merged result. "
                  "Wrong path, or an unsupported language.")
            _report_scan_problems(0)
            sys.exit(2)

        changed, removed = diff_snapshots(before, after)
        if not changed and not removed:
            print(f"No logic drift. ({len(before)} symbols compared)")
        if changed:
            print(f"## Changed logic ({len(changed)})")
            for key, b, a in changed[:MAX_DETAIL]:
                print(f"\n### {key}")
                print("--- before ---")
                print(_clip(b))
                print("--- after ---")
                print(_clip(a))
            if len(changed) > MAX_DETAIL:
                print(f"\n### {len(changed) - MAX_DETAIL} more (names only, see the files)")
                for key, _, _ in changed[MAX_DETAIL:]:
                    print(f"- {key}")
        if removed:
            print(f"\n## Disappeared in the merge ({len(removed)})")
            for key in removed:
                print(f"- {key}")

        wiring_before = [k for k in before if k.endswith(MODULE_CODE_KEY)]
        if wiring_before:
            print(f"\n## Top-level wiring ({len(wiring_before)} place(s), check by eye)")
            print("   Listener hookups and init order. Merging always rewrites this, so it is")
            print("   kept out of the change count - but broken buttons start here.")
            for key in wiring_before:
                print(f"- {key}")

        before_names = {k.split("::")[-1] for k in before}
        added = sorted(k for k in after if k.split("::")[-1] not in before_names)
        if added:
            print(f"\n## New in the merge ({len(added)}, informational)")
            for key in added:
                print(f"- {key}")
        _report_scan_problems(len(after))


if __name__ == "__main__":
    main()
