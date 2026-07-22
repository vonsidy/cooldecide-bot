"""compute_learning: the dashboard's Learning panel was frozen at zeros.

`data.setdefault("learning", _empty_learning())` was the only write, and
setdefault fires only when the key is absent — so the stub was written on run
one and never recomputed. The panel read "0 old enough to score" with three
qualifying videos in the same file, and would have forever.
"""
import ast
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load compute_learning without importing dashboard.py (it pulls in content/config).
_SRC = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "dashboard.py"), encoding="utf-8").read()
_NS = {"datetime": datetime}
for _node in ast.parse(_SRC).body:
    if isinstance(_node, ast.Assign) or (
            isinstance(_node, ast.FunctionDef) and _node.name == "compute_learning"):
        try:
            exec(compile(ast.Module([_node], []), "<dashboard>", "exec"), _NS)
        except Exception:
            pass
compute_learning = _NS["compute_learning"]

NOW = datetime.datetime.now(datetime.timezone.utc)


def vid(days_old, theme, views):
    return {"date": (NOW - datetime.timedelta(days=days_old)).isoformat(),
            "theme": theme, "views": views}


def test_only_mature_videos_score():
    v = [vid(0.2, "A", 999), vid(2.9, "A", 999), vid(3.1, "A", 10), vid(9, "A", 20)]
    out = compute_learning(v)
    assert out["trained_on"] == 2, out          # 3.1d and 9d only
    assert out["counts"]["theme"]["A"] == 2
    print("only videos past min_age_days are scored          OK")


def test_ranks_on_mean_not_total():
    """Totals would just rank whichever theme was posted most — the same
    age-bias the maturity gate exists to remove, moved to the other axis."""
    v = [vid(5, "Posted a lot", 100), vid(5, "Posted a lot", 100),
         vid(5, "Posted a lot", 100), vid(5, "Posted a lot", 100),
         vid(5, "Actually better", 500), vid(5, "Actually better", 500)]
    out = compute_learning(v)
    assert out["best_theme"] == "Actually better", out["themes"]
    assert out["themes"]["Actually better"] > out["themes"]["Posted a lot"]
    print("ranks on mean views, not volume                   OK")


def test_thin_theme_gets_no_weight():
    """One lucky video is a coincidence; publishing it as 'your best style'
    would steer the bot off a sample of one."""
    v = [vid(5, "Solid", 100), vid(5, "Solid", 100), vid(5, "Fluke", 99999)]
    out = compute_learning(v)
    assert "Fluke" not in out["themes"], out["themes"]
    assert out["best_theme"] == "Solid"
    assert out["counts"]["theme"]["Fluke"] == 1, "still counted, just not weighted"
    print("a single-video theme is counted but not weighted  OK")


def test_ready_requires_enough_scored():
    thin = compute_learning([vid(5, "A", 10), vid(5, "A", 10), vid(5, "A", 10)])
    assert thin["trained_on"] == 3 and not thin["ready"], thin
    ok = compute_learning([vid(5, "A", 10), vid(5, "A", 10),
                           vid(5, "B", 20), vid(5, "B", 20)])
    assert ok["trained_on"] == 4 and ok["ready"], ok
    print("ready flips only at NEEDS scored videos           OK")


def test_survives_junk_records():
    v = [vid(5, "A", 10), vid(5, "A", 10),
         {"date": "not-a-date", "theme": "A", "views": 5},
         {"theme": "A", "views": 5},                    # no date
         {"date": (NOW - datetime.timedelta(days=5)).isoformat(), "views": 5},  # no theme
         {"date": (NOW - datetime.timedelta(days=5)).isoformat(),
          "theme": "A", "views": None}]                 # never-fetched views
    out = compute_learning(v)
    assert out["trained_on"] == 3, out   # two good + the None-views one
    print("unparseable / incomplete records are skipped      OK")


def test_no_videos_is_not_a_crash():
    out = compute_learning([])
    assert out["trained_on"] == 0 and out["themes"] == {} and not out["ready"]
    assert compute_learning(None)["trained_on"] == 0
    print("empty and None inputs return an honest zero       OK")


for fn in (test_only_mature_videos_score, test_ranks_on_mean_not_total,
           test_thin_theme_gets_no_weight, test_ready_requires_enough_scored,
           test_survives_junk_records, test_no_videos_is_not_a_crash):
    fn()
print("\nPASS")
