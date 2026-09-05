# Cooker

**Catch the logic that quietly changes when an AI merges your parallel work.**

You split a prototype into parts and built them separately — different sessions, different
people, different AI agents. Then you ask an AI to combine them. The merged file runs, the UI
looks right, and somewhere in the middle a guard clause is gone, a threshold moved from `0.3`
to `0.5`, and a `>=` became `>`.

Nothing crashes. That is the problem.

Cooker snapshots the behavior of every function, class, constant and type contract **before**
the merge, compares it against the merged result, and reports only what actually changed.
Formatting, comments, quote style and renamed Python locals are filtered out.

It is a [Claude Code](https://code.claude.com/docs) plugin, but the script underneath is plain
Python with no dependencies, so any agent — or any human — can run it.

---

## When to use it

Cooker is for **combining code that was never a branch of anything**. The pieces evolved
independently, so they duplicate each other, disagree on interfaces, and have to be rewritten
as they are joined. That rewriting is where behavior silently drifts.

**Good fits:**

- *"I had three Claude sessions build the parser, the scheduler and the UI. Merge them."*
  Each part invented its own config constants. Cooker tells you which ones vanished.
- *"Two teammates prototyped the same screen. Take the best of both."*
  Both wrote `formatPrice`. One rounds, one truncates. Only one survives the merge — cooker
  shows you which behavior you just threw away.
- *"I refactored these five files into one module."*
  Cooker follows symbols across the reorganization and confirms the other 40 functions are
  untouched, so you only review the 5 that moved.
- *"An agent 'cleaned up duplicates' in my codebase."*
  Diff the before-snapshot against the result and see exactly what "cleanup" meant.

**Not a fit:**

- **Git merge conflicts.** Same repo, shared history, conflict markers — use your merge tool.
  Cooker is for code that has no common ancestor.
- **Reviewing normal edits.** If you wrote the change deliberately, you already know what
  changed. Cooker earns its keep when *something else* did the rewriting.
- **Languages it cannot read.** Java, Go, C#, CSS produce zero symbols — and cooker says so
  loudly instead of reporting success.

---

## Install

**As a Claude Code plugin (recommended):**

```
/plugin marketplace add ziezo/cooker
/plugin install cooker@cooker
```

**As a personal skill, without the plugin system:**

```bash
git clone https://github.com/ziezo/cooker /tmp/cooker
cp -r /tmp/cooker/plugins/cooker/skills/cooker ~/.claude/skills/cooker
```

Restart Claude Code afterwards — the skill list is cached at startup.

**Standalone, for any other agent or for scripting** — the script has no dependencies:

```bash
python plugins/cooker/skills/cooker/logic_snapshot.py --help
```

Python 3.8+, no third-party packages. Developed and tested on Python 3.14 (Windows).

---

## How you actually use it

### With Claude Code

Just ask for the merge. The skill triggers on requests like "combine these", "merge these
parts", "make this one file", "integrate the two versions".

```
merge ./parser ./scheduler ./ui into ./app.py
```

Claude snapshots the three parts, does the merge, diffs the result, and comes back with
something like:

> Merged into `app.py`. Cooker flagged 3 changes:
> - `scheduler.py::retry_delay` — backoff constant changed 0.5 → 1.0. **Was this intended?**
> - `parser.py::parse_line` — now returns an object instead of a dict (needed to match the UI)
> - `ui.py::RETRY_LIMIT` — disappeared, superseded by scheduler's own limit

You confirm or reject each one. Anything unintended gets reverted before you ever run the code.

### Telling it *how* to merge

Anything you type after the paths is a merge instruction, and cooker uses it to decide what
needs your confirmation and what does not:

```
/cooker ./v1 ./v2 unify on v2's state management, but keep v1's error handling
```

Changes that the instruction explains are reported as "changed as instructed" and passed over.
Only the changes you did *not* ask for come back as questions.

### By hand

```bash
SNAP=plugins/cooker/skills/cooker/logic_snapshot.py

# 1. before you merge anything
python $SNAP snapshot ./partA ./partB ./partC -o before.json

# 2. merge however you like

# 3. after
python $SNAP diff before.json ./merged.py
```

One rule: **keep the original pieces.** If the merge overwrites them, there is nothing left to
compare against.

---

## Walkthrough

`examples/python-log-analyzer/` holds three parts of a log analyzer built separately, plus a
correct merge and a deliberately damaged one.

```bash
cd examples/python-log-analyzer
SNAP=../../plugins/cooker/skills/cooker/logic_snapshot.py
python $SNAP snapshot part1_parse.py part2_aggregate.py part3_report.py -o before.json
python $SNAP diff before.json merged.py
```

```
## Changed logic (5)

### part2_aggregate.py::count_by_level
--- before ---
  | def count_by_level(entries):
  |     counts = {}
  |     for entry in entries:
  |         counts[entry["level"]] = counts.get(entry["level"], 0) + 1
  |     return counts
--- after ---
  | def count_by_level(entries):
  |     counts = {}
  |     for entry in entries:
  |         counts[entry.level] = counts.get(entry.level, 0) + 1
  |     return counts
...
## Disappeared in the merge (1)
- part2_aggregate.py::DEMO

## Top-level wiring (3 place(s), check by eye)
...
## New in the merge (2, informational)
- merged.py::analyze
- merged.py::format_sources
```

Part 2 was written against dicts while part 1 produces objects, so the merge had to adapt it.
Cooker points at exactly the five functions that were touched — and stays quiet about the
twenty-odd that were not.

Now the damaged merge, which runs without errors and prints a plausible report:

```bash
python $SNAP snapshot merged.py -o good.json
python $SNAP diff good.json merged_broken.py
```

```
## Changed logic (5)
### merged.py::error_ratio        <- empty-input guard deleted
### merged.py::should_alert       <- >= became >
### merged.py::top_sources        <- off-by-one in the slice
### merged.py::make_bar           <- round() became truncation
### merged.py::ALERT_THRESHOLD    <- 0.3 became 0.5
```

Five planted bugs, five caught. The function whose comments and blank lines were rewritten is
not in the list.

### The React example

`examples/react-shop/` is the same story in JSX: a cart part and a checkout part that each
implemented the money math, with their own tax constant. The merge unified them on part 1.

```
## Changed logic (3)
### part2_list.jsx::ProductList     <- default export moved to the page component
### part3_checkout.jsx::orderTotal  <- now goes through subtotal/shippingFee
### part3_checkout.jsx::Checkout    <- price formatting unified

## Disappeared in the merge (1)
- part3_checkout.jsx::VAT_RATE      <- duplicate of TAX_RATE, removed
```

The duplicated constant vanishing is the interesting line. It is correct here, and a silent bug
the next time.

---

## What it tracks

| | |
|---|---|
| Functions, classes, methods | Python via `ast` (exact); JS/TS via pattern matching |
| Decorators | `@cache` disappearing is a behavior change |
| Top-level constants | including TypeScript's `const X: T = ...` |
| Type contracts | `interface`, `type` aliases, `enum` |
| HTML | code inside `<script>` |

Symbols are followed across file reorganization (three parts collapsing into one file) and
across renames, so restructuring alone does not produce noise.

Supported: `.py` `.js` `.ts` `.jsx` `.tsx` `.html`

## What it does not do

- **JS/TS local renames read as changes.** Python normalizes locals through the AST and is
  immune; JavaScript has no stdlib parser here, so `counts` → `result` is reported.
- **Equivalent code written differently reads as a change** — f-string vs `.format()`, ternary
  vs if/else. Deliberately not "fixed": teaching the tool to call two different things equal
  risks hiding a real bug, and a false positive only costs ten seconds of reading.
- **Top-level wiring is reported separately, never counted as a change.** Listener hookups and
  init order always change when files are combined, so counting them would bury the signal.
  Check that section by eye — broken buttons live there.
- Cross-file call relationships are not tracked.
- It never edits your code. Cooker only reads and prints.

## Failing loudly

The worst outcome for a tool like this is a confident "all clear" on a check that never ran. A
typo'd path, an unsupported language, an unreadable file, a corrupt snapshot or swapped
arguments all print a `!!` line and exit non-zero, and the skill instructions tell the agent
never to report those as a pass.

```
$ python logic_snapshot.py snapshot ./typoed-path -o before.json
!! Path not found (typo, or not created yet):
  - ./typoed-path
$ echo $?
2
```

## Development

```bash
python plugins/cooker/skills/cooker/test_logic_snapshot.py   # 29 asserts, no framework
```

Every fix in this repo started as a bug found by running the tool against real merges: a
destructured React parameter truncating a function body, a URL's `//` swallowing the rest of a
line, Python's floor-division operator read as a JS comment, look-alike helpers hiding a
300-symbol regression. Each one has a regression assert.

Validated against 15 three-way merge scenarios across HTML, Python, JS, TS, JSX and Node, plus
a 6000-symbol synthetic project (0.3s).

## License

MIT — provided as is, without warranty of any kind. See [LICENSE](LICENSE).
