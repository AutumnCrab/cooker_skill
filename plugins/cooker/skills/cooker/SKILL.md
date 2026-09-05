---
name: cooker
description: Catches logic that quietly changes or disappears when separately built code pieces (written in different sessions, by different people, or by different AI agents; prototype parts; separate folders rather than branches) are merged into one. Design, style and naming differences are ignored. Use for requests like "merge these", "combine", "make this one file", "join these parts", "integrate the two versions", "clean up the duplicates into one".
---

# Cooker - keep logic intact when merging parallel work

## When to use
When the user asks to combine several code pieces that were built independently (different
sessions, different people, different AI agents). Resolving a git merge conflict inside one
repository is NOT this - ordinary merge tools handle that. This skill exists to catch the AI
silently altering behavior while merging.

## Merge direction (free text after the paths)
Text after the paths is an instruction about how to merge. For example:
```
/cooker ./partA ./partB unify on partA's state management, take only the UI from partB
/cooker ./v1 ./v2 keep v2 where they overlap, but keep v1's error handling
```
- Follow that instruction while merging.
- In step 4, when cooker flags drift that the instruction explains, report it as
  "changed as instructed" and move on. Only ask the user about changes the instruction
  does not cover.
- With no instruction, the default is "preserve the original logic".

## Principle
Ignore design, formatting and naming. Only check whether the actual behavior of
functions, classes, constants and type contracts changed between before and after.

## Procedure
`<skill dir>` below is the directory holding this SKILL.md (see "Base directory for this
skill" at the top of the prompt). Always quote paths - they may contain spaces or
non-ASCII characters. If `python` is missing, try `python3`; if neither exists, tell the
user cooker cannot run and just do the merge.

1. **Before merging**, snapshot every piece in one call (multiple paths, files or dirs):
   ```
   python "<skill dir>/logic_snapshot.py" snapshot "<piece1>" "<piece2>" "<piece3>" -o "<tmp>/before.json"
   ```
   **Careful**: if the merged file will live in the same folder as the pieces, list the piece
   files explicitly instead of the folder. If the merged file ends up inside the before-snapshot,
   drift can never be detected.

2. Merge as you normally would.

3. **Right after merging**, compare against the merged result directly:
   ```
   python "<skill dir>/logic_snapshot.py" diff "<tmp>/before.json" "<merged file or dir>"
   ```

4. **If any line starts with `!!`, or the exit code is not 0, the check did not happen.**
   Zero symbols, unsupported language, unreadable files. In that case **never report
   "cooker passed" or "no issues"**. Say the check could not run, and why.

5. When "Changed logic" or "Disappeared in the merge" appears, **confirm with the user that
   each one was intended.** Revert anything unintended. Never pass over it silently.
   Long bodies are clipped with `... (N lines omitted)`; open the file when unsure.

6. Formatting, comment and whitespace differences are filtered out already - do not ask
   the user about those.

## What is tracked
- Functions and classes (Python via `ast`, JS/TS via pattern matching)
- Top-level constants, including type-annotated ones, and Python module-level assignments
- TypeScript contracts: `interface`, `type` aliases, `enum`
- Code inside `<script>` in HTML

Symbols are followed across file reorganization (three parts into one file) and renames.

## The snapshot file holds their source code
`before.json` stores function bodies and constants **verbatim** — including any secret that is
hardcoded as a constant. Treat it like the source itself:
- write it to a temp/scratch directory, never inside the user's repository
- delete it once the merge is confirmed
- never commit it, never paste its contents anywhere

## Keep the original pieces
**Do not overwrite or delete the original piece files.** Always write the merged result to a
new file. Without the originals there is nothing to compare against.

## Known limits
- **Renaming a local variable or parameter is reported as a change in JS/TS** (false positive).
  Python is immune - locals are normalized via AST. Read the diff and say so when it is a
  false positive; do not silently ignore it, and do not blindly revert it.
- **Equivalent code written differently is also a false positive** - f-string vs `.format()`,
  ternary vs if/else. Same handling: read it, judge it, say what you found.
- Quote style, whitespace, indentation and comments are ignored (not false positives).
- Python uses `ast` and is exact. JS/TS uses patterns plus brace counting - not a real parser.
- **Top-level wiring is reported separately, not counted as a change** - listener hookups and
  init order always change when files are combined. Broken buttons start there, so check it
  by eye in the merged file.
- Supported languages: Python, JS/TS/JSX/TSX, and `<script>` in HTML. Anything else (Java, Go,
  C#, CSS) produces no symbols - tell the user this skill cannot verify their merge.
- Changes in cross-file call relationships are not tracked.
- Symbols shorter than 10 tokens are not followed across renames, to avoid accidental matches.
- Other agent environments (Codex and friends) will not auto-discover this skill, but
  `logic_snapshot.py` runs anywhere Python does - point them at this file or hand them the
  two commands above.
