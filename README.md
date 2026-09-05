# Cooker

**Merge code that was built separately — without the logic quietly changing on the way in.**

Ask an AI to combine three prototype parts and you get one file back. It runs. The UI looks
right. And somewhere in the middle a guard clause is gone, a threshold moved from `0.3` to
`0.5`, and a `>=` became `>` — because merging is rewriting, and rewriting drifts.

Nothing crashes. That is the problem.

Cooker is the merge. You point it at the pieces, it combines them, and it holds itself
accountable: every function, class, constant and type contract is recorded before the merge and
checked against the result afterwards. Anything whose behavior moved comes back to you as a
question instead of shipping silently.

```
> merge ./parser ./scheduler ./ui into ./app.py

Merged into app.py. Three behaviors changed on the way in:

  scheduler.py::retry_delay   backoff constant 0.5 -> 1.0        <- was this intended?
  parser.py::parse_line       returns an object now, not a dict  <- needed to match the UI
  ui.py::RETRY_LIMIT          gone, superseded by scheduler's

The other 41 symbols came through unchanged.
```

You answer, unintended changes get reverted, and only then do you run the code.

It is a [Claude Code](https://code.claude.com/docs) plugin. To be exact about what ships here:
the merging is done by the agent following the skill's instructions, and the Python in this repo
is the half that holds it accountable — it records and compares, and never rewrites a line. That
split is deliberate. The thing doing the rewriting should not also be the thing grading it.

The engine has no dependencies, so you can drive it by hand or from another agent too.

---

## When to reach for it

Cooker is for **combining code that was never a branch of anything**. The pieces grew
independently, so they duplicate each other, disagree on interfaces, and have to be rewritten
as they are joined. That is exactly where behavior slips.

- *"Three Claude sessions built the parser, the scheduler and the UI. Put them together."*
  Each part invented its own config constants. Cooker merges them and tells you which ones it
  had to drop.
- *"Two teammates prototyped the same screen. Take the best of both."*
  Both wrote `formatPrice` — one rounds, one truncates. Only one can survive; cooker makes sure
  you are the one who decides which.
- *"Fold these five files into one module."*
  Cooker follows every symbol across the reorganization, so you review the 5 that genuinely
  changed instead of re-reading all 45.
- *"An agent already 'cleaned up the duplicates' — what did it actually do?"*
  Snapshot the originals, diff the result, and read the answer.

**Not this:**

- **Git merge conflicts.** Same repo, shared history, conflict markers — use your merge tool.
  Cooker is for code with no common ancestor.
- **Edits you made yourself.** You already know what you changed.
- **Languages it cannot read.** Java, Go, C#, CSS produce zero symbols — and cooker says so
  loudly rather than reporting a clean merge.

---

## Install

**As a Claude Code plugin (recommended):**

```
/plugin marketplace add AutumnCrab/cooker_skill
/plugin install cooker@cooker
```

**As a personal skill, without the plugin system:**

```bash
git clone https://github.com/AutumnCrab/cooker_skill /tmp/cooker
cp -r /tmp/cooker/plugins/cooker/skills/cooker ~/.claude/skills/cooker
```

Restart Claude Code afterwards — the skill list is cached at startup.

Python 3.8+, no third-party packages. Developed and tested on Python 3.14 (Windows).

---

## Using it

### Just ask for the merge

The skill triggers on ordinary requests — "combine these", "merge these parts", "make this one
file", "integrate the two versions", "clean up the duplicates into one".

```
merge ./partA ./partB ./partC into ./merged.py
```

Cooker records the parts, merges them, verifies the result, and reports every behavior that
moved. Formatting, comments, quote style and renamed Python locals never show up — only real
changes do.

### Steer how it merges

Anything after the paths is an instruction, and cooker uses it to decide what needs your
approval and what does not:

```
/cooker ./v1 ./v2 unify on v2's state management, but keep v1's error handling
```

Changes the instruction explains come back as *"changed as instructed"* and are passed over.
Only the ones you did not ask for become questions.

### Two rules

**Keep the originals.** Cooker writes the merge to a new file and never touches your pieces —
they are the baseline it checks against. If something else overwrites them, there is nothing
left to compare.

**Treat the snapshot like source code.** `before.json` contains function bodies and constants
verbatim, so a hardcoded credential in your code is a hardcoded credential in the snapshot.
Write it to a temp directory, keep it out of version control, and delete it once the merge is
confirmed. The tool prints this reminder every time it writes one, and the repo's `.gitignore`
already covers the default names.

### Driving it by hand

The engine is a standalone script, useful from other agents, CI, or a shell:

```bash
SNAP=plugins/cooker/skills/cooker/logic_snapshot.py

python $SNAP snapshot ./partA ./partB ./partC -o before.json   # before you merge
# ... merge however you like ...
python $SNAP diff before.json ./merged.py                      # after
```

---

## What a merge report looks like

`examples/python-log-analyzer/` holds three parts of a log analyzer built separately, plus the
merged result.

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
Cooker names exactly the five functions it touched — and stays quiet about the twenty-odd it
carried through untouched.

### Proving it catches the bad merge

`merged_broken.py` is the same merge with five subtle bugs planted. It runs fine and prints a
plausible report:

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

Five planted, five caught. The function whose comments and blank lines were rewritten is not in
the list.

### The React example

`examples/react-shop/` is the same story in JSX: a cart part and a checkout part that each
implemented the money math with their own tax constant. The merge unified them on part 1.

```
## Changed logic (3)
### part2_list.jsx::ProductList     <- default export moved to the page component
### part3_checkout.jsx::orderTotal  <- now goes through subtotal/shippingFee
### part3_checkout.jsx::Checkout    <- price formatting unified

## Disappeared in the merge (1)
- part3_checkout.jsx::VAT_RATE      <- duplicate of TAX_RATE, removed
```

The duplicated constant vanishing is the line worth reading. It is correct here, and a silent
bug the next time.

---

## What it watches

| | |
|---|---|
| Functions, classes, methods | Python via `ast` (exact); JS/TS via pattern matching |
| Decorators | `@cache` disappearing is a behavior change |
| Top-level constants | including TypeScript's `const X: T = ...` |
| Type contracts | `interface`, `type` aliases, `enum` |
| HTML | code inside `<script>` |

Symbols are followed across file reorganization (three parts collapsing into one) and across
renames, so restructuring alone produces no noise.

Supported: `.py` `.js` `.ts` `.jsx` `.tsx` `.html`

## What it will not catch

- **JS/TS local renames read as changes.** Python normalizes locals through the AST and is
  immune; JavaScript has no stdlib parser here, so `counts` → `result` is reported.
- **Equivalent code written differently reads as a change** — f-string vs `.format()`, ternary
  vs if/else. Deliberately not "fixed": teaching the tool to call two different things equal
  risks hiding a real bug, and a false positive costs ten seconds of reading.
- **Top-level wiring is reported separately, never counted as a change.** Listener hookups and
  init order always change when files are combined, so counting them would bury the signal.
  Read that section by eye — broken buttons live there.
- Cross-file call relationships are not tracked.
- **JS/TS is read by pattern matching, not a real parser.** It is exercised by 22 adversarial
  syntax cases in the test suite — async functions, generators, decorated classes, nested
  template literals, JSX braces, regexes containing quotes — but a syntax nobody thought of can
  still slip past. This is the least trustworthy part of the tool; treat Python results as
  exact and JS/TS results as very good but not proof.
- The verification engine never edits code. It only reads and prints.

## Failing loudly

The worst outcome for a tool like this is a confident "all clear" on a check that never ran. A
typo'd path, an unsupported language, an unreadable file, a corrupt snapshot or swapped
arguments all print a `!!` line and exit non-zero, and the skill instructions tell the agent
never to report those as a successful merge.

```
$ python logic_snapshot.py snapshot ./typoed-path -o before.json
!! Path not found (typo, or not created yet):
  - ./typoed-path
$ echo $?
2
```

## Development

```bash
python plugins/cooker/skills/cooker/test_logic_snapshot.py   # 31 asserts + 22 JS syntax cases
```

Every fix in this repo started as a bug found by merging real code: a destructured React
parameter truncating a function body, a URL's `//` swallowing the rest of a line, Python's
floor-division operator read as a JS comment, look-alike helpers hiding a 300-symbol
regression. Each one left a regression assert behind.

Validated on 15 three-way merges across HTML, Python, JS, TS, JSX and Node, plus a
6000-symbol synthetic project (0.3s).

## License

MIT — provided as is, without warranty of any kind. See [LICENSE](LICENSE).
