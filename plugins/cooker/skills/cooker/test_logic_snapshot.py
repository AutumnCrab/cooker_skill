"""assert-based self check. Run: python test_logic_snapshot.py"""
import os
import shutil
import tempfile

from logic_snapshot import _extract_js, diff_snapshots, snapshot

tmp = tempfile.mkdtemp()
try:
    before_dir = os.path.join(tmp, "before")
    after_dir = os.path.join(tmp, "after")
    os.makedirs(before_dir)
    os.makedirs(after_dir)

    with open(os.path.join(before_dir, "calc.py"), "w", encoding="utf-8") as f:
        f.write("def add(a, b):\n    return a + b\n\ndef unused():\n    pass\n")

    # after: logic really changed (+ became -), and `unused` was dropped during the merge
    with open(os.path.join(after_dir, "calc.py"), "w", encoding="utf-8") as f:
        f.write("def add(a, b):\n    # a comment must not matter\n    return a - b\n")

    before = snapshot(before_dir)
    after = snapshot(after_dir)
    assert "calc.py::add" in before and "calc.py::unused" in before

    changed, removed = diff_snapshots(before, after)
    changed_keys = [k for k, _, _ in changed]
    assert "calc.py::add" in changed_keys, changed_keys
    assert "calc.py::unused" in removed, removed

    # formatting-only differences are not changes
    before2 = {"x.py::f": "def f(a):\n    return a+1\n"}
    after2 = {"x.py::f": "def f(a):\n\n    # comment\n    return a + 1  # style only\n"}
    changed2, removed2 = diff_snapshots(before2, after2)
    assert changed2 == [] and removed2 == [], (changed2, removed2)

    # code inside <script> must be extracted
    html_dir = os.path.join(tmp, "html")
    os.makedirs(html_dir)
    with open(os.path.join(html_dir, "app.html"), "w", encoding="utf-8") as f:
        f.write("<html><body><script>\nfunction render(x) {\n  return x * 2;\n}\n</script></body></html>\n")
    assert "app.html::render" in snapshot(html_dir)

    # a symbol that moved file (part1.html -> merged.html) is found by name
    before3 = {"part1.html::calc": "function calc(a){return a+1;}"}
    same_moved = {"merged.html::calc": "function calc(a) {\n  return a + 1;\n}"}
    changed3, removed3 = diff_snapshots(before3, same_moved)
    assert changed3 == [] and removed3 == [], (changed3, removed3)

    # moved AND changed must still be reported
    changed_moved = {"merged.html::calc": "function calc(a) {\n  return a - 1;\n}"}
    changed4, removed4 = diff_snapshots(before3, changed_moved)
    assert len(changed4) == 1 and removed4 == [], (changed4, removed4)

    # logic that was only renamed counts as preserved
    before5 = {"part2.html::formatNumber": "function formatNumber(n){return n*2;}"}
    renamed5 = {"merged.html::formatTemperature": "function formatTemperature(n) { return n * 2; }"}
    changed5, removed5 = diff_snapshots(before5, renamed5)
    assert changed5 == [] and removed5 == [], (changed5, removed5)

    # even if the name now points at different logic, the original surviving elsewhere counts
    before6 = {"part2.html::fmt": "function fmt(n){return n*2;}"}
    after6 = {
        "merged.html::fmt": "function fmt(n) { return n * 3; }",
        "merged.html::fmtTemp": "function fmtTemp(n) { return n * 2; }",
    }
    changed6, removed6 = diff_snapshots(before6, after6)
    assert changed6 == [] and removed6 == [], (changed6, removed6)

    # quote style is not logic
    before7 = {"a.py::f": 'def f():\n    return "hi"\n'}
    after7 = {"a.py::f": "def f():\n    return 'hi'\n"}
    changed7, removed7 = diff_snapshots(before7, after7)
    assert changed7 == [] and removed7 == [], (changed7, removed7)

    # // inside a URL string is not a comment - the endpoint change must be caught
    url_a = {"x.js::f": 'function f() { return fetch("https://api.example.com/v1/users"); }'}
    url_b = {"x.js::f": 'function f() { return fetch("https://api.example.com/v1/ADMIN"); }'}
    changed8, _ = diff_snapshots(url_a, url_b)
    assert len(changed8) == 1, changed8

    # real comments are still ignored
    cmt_a = {"x.js::f": "function f() { return 1; }"}
    cmt_b = {"x.js::f": "function f() {\n  // explain\n  return 1; // trailing\n}"}
    changed9, removed9 = diff_snapshots(cmt_a, cmt_b)
    assert changed9 == [] and removed9 == [], (changed9, removed9)

    # an unbalanced brace inside a string must not truncate the body
    brace_code = 'function render(x) {\n  return "{ open brace";\n}\nfunction tail(y) { return y; }'
    extracted = _extract_js(brace_code)
    assert len(extracted["render"].splitlines()) == 3, extracted["render"]
    assert "tail" in extracted, list(extracted)

    # # inside a JS regex is not a comment
    re_code = ('function pick(t) {\n  return t.filter(function (c) '
               '{ return /^#[0-9a-fA-F]{6}$/.test(c); });\n}\nfunction next(x) { return x; }')
    picked = _extract_js(re_code)
    assert len(picked["pick"].splitlines()) == 3, picked["pick"]
    assert "next" in picked, list(picked)

    # // in Python is floor division; treating it as a comment would hide the change
    fd_a = {"m.py::f": "def f(a, b):\n    return a // b\n"}
    fd_b = {"m.py::f": "def f(a, b):\n    return a / b\n"}
    changed10, _ = diff_snapshots(fd_a, fd_b)
    assert len(changed10) == 1, changed10

    # decorators are logic - losing @cache must be caught
    dec_dir = os.path.join(tmp, "dec")
    os.makedirs(dec_dir)
    dec_file = os.path.join(dec_dir, "d.py")
    with open(dec_file, "w", encoding="utf-8") as f:
        f.write("import functools\n\n@functools.cache\ndef heavy(n):\n    return n * 2\n")
    dec_before = snapshot(dec_file)
    assert "@functools.cache" in dec_before["d.py::heavy"], dec_before
    with open(dec_file, "w", encoding="utf-8") as f:
        f.write("import functools\n\ndef heavy(n):\n    return n * 2\n")
    changed11, _ = diff_snapshots(dec_before, snapshot(dec_file))
    assert len(changed11) == 1, changed11

    # same-named methods on different classes must not overwrite each other
    cls_file = os.path.join(dec_dir, "c.py")
    with open(cls_file, "w", encoding="utf-8") as f:
        f.write("class A:\n    def run(self):\n        return 1\n\nclass B:\n    def run(self):\n        return 2\n")
    cls_before = snapshot(cls_file)
    assert "c.py::A.run" in cls_before and "c.py::B.run" in cls_before, sorted(cls_before)
    with open(cls_file, "w", encoding="utf-8") as f:
        f.write("class A:\n    def run(self):\n        return 1\n\nclass B:\n    def run(self):\n        return 999\n")
    changed12, _ = diff_snapshots(cls_before, snapshot(cls_file))
    assert [k for k, _, _ in changed12] == ["c.py::B.run"], changed12

    # a name declared twice in one file keeps both
    dup_file = os.path.join(dec_dir, "dup.js")
    with open(dup_file, "w", encoding="utf-8") as f:
        f.write("function f() { return 1; }\nfunction f() { return 2; }\n")
    dup = snapshot(dup_file)
    assert "dup.js::f" in dup and "dup.js::f#2" in dup, sorted(dup)

    # named export default must not be registered twice; anonymous one must be caught
    named_file = os.path.join(dec_dir, "n.jsx")
    with open(named_file, "w", encoding="utf-8") as f:
        f.write("export default function Named({ a }) {\n  return a;\n}\n")
    assert sorted(snapshot(named_file)) == ["n.jsx::Named"], sorted(snapshot(named_file))
    anon_file = os.path.join(dec_dir, "a.jsx")
    with open(anon_file, "w", encoding="utf-8") as f:
        f.write("export default () => {\n  return 1;\n};\n")
    assert "a.jsx::default" in snapshot(anon_file)

    # many look-alike helpers must not be mistaken for a rename and hide a real change
    twin_before = {"p.py::a": "def a(x):\n    return x * 1 + 0\n"}
    twin_after = {
        "m.py::a": "def a(x):\n    return x * 2 + 0\n",
        "m.py::b": "def b(x):\n    return x * 1 + 0\n",
        "m.py::c": "def c(x):\n    return x * 1 + 0\n",
    }
    changed13, _ = diff_snapshots(twin_before, twin_after)
    assert len(changed13) == 1, changed13

    # a destructured parameter's brace must not be mistaken for the function body
    destr = _extract_js("function Row({ product, onAdd }) {\n  return product.id;\n}\n")
    assert destr["Row"].rstrip().endswith("}"), destr
    assert "return product.id" in destr["Row"], destr

    # renaming Python locals is not a logic change
    ren_a = {"m.py::f": "def f(items):\n    counts = {}\n    for i in items:\n        counts[i] = 1\n    return counts\n"}
    ren_b = {"m.py::f": "def f(items):\n    result = {}\n    for x in items:\n        result[x] = 1\n    return result\n"}
    changed14, removed14 = diff_snapshots(ren_a, ren_b)
    assert changed14 == [] and removed14 == [], (changed14, removed14)

    # swapped operands are a real change, name normalization must not hide it
    ord_a = {"m.py::g": "def g(a, b):\n    return a - b\n"}
    ord_b = {"m.py::g": "def g(a, b):\n    return b - a\n"}
    changed15, _ = diff_snapshots(ord_a, ord_b)
    assert len(changed15) == 1, changed15

    print("OK: all self-checks passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
