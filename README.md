# Cooker

**Catch the logic that quietly changes when an AI merges your parallel work.**

You split a prototype into parts and built them separately — different sessions, different
people, different AI agents. Then you ask an AI to combine them. The merged file runs, the
UI looks right, and somewhere in the middle a guard clause is gone, a threshold moved from
`0.3` to `0.5`, and a `>=` became `>`.

Nothing crashes. That is the problem.

Cooker snapshots the behavior of every function, class, constant and type contract **before**
the merge, then compares it against the merged result and reports only what actually changed.
Formatting, comments, quote style and renamed locals are filtered out.

This is a [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills), but the
script underneath is plain Python with no dependencies, so any agent or human can run it.

## Not a merge-conflict tool

Git merge conflicts inside one repository are already well served. Cooker is for the other
case: **two or more independently written code bases that were never branches of each other**,
being combined by an agent that is free to rewrite as it goes.

## Install

As a personal Claude Code skill:

```bash
git clone https://github.com/<you>/cooker-skill ~/.claude/skills/cooker
```

Restart Claude Code (the skill list is cached at startup). Then merging requests such as
"combine these three parts" trigger it automatically, or invoke it with `/cooker`.

Standalone, for any other agent or by hand — just run the script:

```bash
python logic_snapshot.py snapshot ./partA ./partB ./partC -o /tmp/before.json
# ... merge into merged.py ...
python logic_snapshot.py diff /tmp/before.json ./merged.py
```

Requires Python 3.8+. No third-party packages.

## Walkthrough

`examples/python-log-analyzer/` holds three parts of a log analyzer built separately, plus a
correct merge and a deliberately damaged one.

```bash
cd examples/python-log-analyzer
python ../../logic_snapshot.py snapshot part1_parse.py part2_aggregate.py part3_report.py -o before.json
python ../../logic_snapshot.py diff before.json merged.py
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
python ../../logic_snapshot.py snapshot merged.py -o good.json
python ../../logic_snapshot.py diff good.json merged_broken.py
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

The duplicated constant vanishing is the interesting line. It is the kind of thing that is
correct here and a silent bug the next time.

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
- **Equivalent code written differently reads as a change** — f-string vs `.format()`,
  ternary vs if/else. Deliberately not "fixed": teaching the tool to call two different
  things equal risks hiding a real bug, and a false positive only costs you ten seconds of
  reading.
- **Top-level wiring is reported separately, never counted as a change.** Listener hookups and
  init order always change when files are combined, so counting them would bury the signal.
  Check that section by eye — broken buttons live there.
- Cross-file call relationships are not tracked.
- Anything outside the supported languages produces zero symbols — and cooker says so loudly
  rather than reporting success.

## Failing loudly

The worst outcome for a tool like this is a confident "all clear" on a check that never ran.
So a typo'd path, an unsupported language, an unreadable file, a corrupt snapshot or swapped
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
python test_logic_snapshot.py   # 29 asserts, no framework
```

Every fix in this repo started as a bug found by running the tool against real merges: a
destructured React parameter truncating a function body, a URL's `//` swallowing the rest of a
line, Python's floor-division operator read as a JS comment, look-alike helpers hiding a
300-symbol regression. Each one has a regression assert.

Validated against 15 three-way merge scenarios across HTML, Python, JS, TS, JSX and Node,
plus a 6000-symbol synthetic project (0.3s).

## License

MIT
