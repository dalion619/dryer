from pathlib import Path

from dryer.discover import is_test_file, language_of
from dryer.extract import entries_in_source
from dryer.scan import find_duplicates, scan_files

LEFT = """\
class Left {
    int[] Alpha(int[] xs) {
        var ys = Enumerable.Where(xs, Odd);
        return ys.Select(Inc).ToArray();
    }
}
"""

RIGHT = """\
class Right {
    int[] Beta(int[] items) {
        var kept = Enumerable.Where(items, Even);
        return kept.Select(Dec).ToArray();
    }
}
"""


def _write(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")


def _scores(root: Path, threshold: float):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    entries, warnings = scan_files(files, root, min_lines=1, min_nodes=1)
    assert warnings == []
    return [
        (item.language, item.left.file, item.right.file, item.score)
        for item in find_duplicates(entries, threshold=threshold)
    ]


def test_renamed_locals_score_one(tmp_path):
    _write(tmp_path, "Left.cs", LEFT)
    _write(tmp_path, "Right.cs", RIGHT)
    assert _scores(tmp_path, 0.99) == [("csharp", "Left.cs", "Right.cs", 1.0)]


def test_a_different_member_call_lowers_the_score(tmp_path):
    _write(tmp_path, "Left.cs", LEFT)
    _write(tmp_path, "Right.cs", RIGHT.replace("kept.Select(Dec).ToArray()", "kept.OrderBy(Dec).ToList()"))
    [(_, _, _, score)] = _scores(tmp_path, 0.0)
    assert score < 1.0


def test_names_survive_null_conditional_and_generic_calls(tmp_path):
    _write(tmp_path, "A.cs", "class A { int F(Foo f) { return f?.Size<int>(1) ?? 0; } }\n")
    _write(tmp_path, "B.cs", "class B { int G(Foo g) { return g?.Count<int>(2) ?? 0; } }\n")
    [(_, _, _, score)] = _scores(tmp_path, 0.0)
    assert score < 1.0


def test_candidates_are_bodied_members():
    entries, warning = entries_in_source(
        "csharp",
        """\
class Board {
    Board() { Reset(); }
    int Size { get { return size; } set => size = value; }
    void Draw() {
        int Local() => 1;
        System.Func<int> f = () => 2;
    }
    abstract void Clear();
}
""",
        "Board.cs",
        "Board.cs",
    )
    assert warning is None
    assert [entry.start_line for entry in entries] == [2, 3, 3, 4]


def test_discovery_skips_generated_files_and_test_projects():
    assert language_of("src/Board.cs") == "csharp"
    assert language_of("obj/Board.g.cs") is None
    assert language_of("src/Form1.Designer.cs") is None
    assert is_test_file(Path("src/Demo.Tests/BoardTests.cs"))
    assert not is_test_file(Path("src/Demo/Board.cs"))
