"""APG4b 学習用ヘルパー

使い方:
  python tools/apg4b.py new EX5          問題フォルダとひな形を作り、入出力例を取得する
  python tools/apg4b.py build F/EX5.cpp  コンパイルだけする
  python tools/apg4b.py run F/EX5.cpp    コンパイルして実行（入力はキーボードから）
  python tools/apg4b.py test F/EX5.cpp   コンパイルして入出力例で答え合わせ
  python tools/apg4b.py auto F/EX5.cpp   入出力例があれば test、なければ run
"""

import argparse
import ctypes
import html
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEST_URL = "https://atcoder.jp/contests/apg4b/tasks/"
TIME_LIMIT = 2.0  # 秒

# EX問題 → (タスクID, 章, フォルダ名)。フォルダ名は章のページの問題記号（1.01 → B）
EX_TASKS = {
    1: ("APG4b_cv", "1.01", "B"),   2: ("APG4b_cu", "1.02", "C"),
    3: ("APG4b_ct", "1.03", "D"),   4: ("APG4b_cs", "1.04", "E"),
    5: ("APG4b_cr", "1.05", "F"),   6: ("APG4b_cq", "1.06", "G"),
    7: ("APG4b_cp", "1.07", "H"),   8: ("APG4b_co", "1.08", "I"),
    9: ("APG4b_cn", "1.09", "J"),   10: ("APG4b_cm", "1.10", "K"),
    11: ("APG4b_cl", "1.11", "L"),  12: ("APG4b_ck", "1.12", "M"),
    13: ("APG4b_cj", "1.13", "N"),  14: ("APG4b_ci", "1.14", "O"),
    15: ("APG4b_ch", "1.15", "P"),  16: ("APG4b_cg", "2.01", "R"),
    17: ("APG4b_cf", "2.02", "S"),  18: ("APG4b_ce", "2.03", "T"),
    19: ("APG4b_cd", "2.04", "U"),  20: ("APG4b_cc", "2.05", "V"),
    21: ("APG4b_cb", "2.06", "W"),  22: ("APG4b_ca", "3.02", "Z"),
    23: ("APG4b_bz", "3.03", "AA"), 24: ("APG4b_by", "3.04", "AB"),
    25: ("APG4b_bx", "3.05", "AC"), 26: ("APG4b_bw", "3.06", "AD"),
}

# AtCoder の環境（GCC, C++23）に近づけつつ、学習向けにミスを見つけやすくするオプション
CXXFLAGS = [
    "-std=gnu++23",
    "-g",
    "-Wall", "-Wextra",              # 怪しい書き方を警告
    "-D_GLIBCXX_DEBUG",              # vector の範囲外アクセスなどを実行時に検出
    "-finput-charset=UTF-8", "-fexec-charset=UTF-8",  # 日本語の文字化け対策
    "-Wl,--stack,268435456",         # 再帰が深くても落ちにくいようにスタックを 256MB に
    f"-I{ROOT / 'include'}",
]

TEMPLATE = """#include <bits/stdc++.h>
using namespace std;

int main() {
}
"""


def color(text, code):
    return f"\033[{code}m{text}\033[0m"


GREEN, RED, YELLOW, CYAN = "32;1", "31;1", "33;1", "36;1"


def use_utf8_console():
    """Windows のコンソールを UTF-8 にする（日本語の入出力が文字化けしないように）"""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def find_compiler():
    for name in ("g++", r"C:\Program Files (x86)\mingw64\bin\g++.exe"):
        path = shutil.which(name) or (name if Path(name).exists() else None)
        if path:
            return path
    sys.exit(color("g++ が見つかりません。MinGW をインストールして PATH を通してください。", RED))


def exe_path(src: Path) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return src.parent / "output" / (src.stem + suffix)


def tests_dir(src: Path) -> Path:
    return src.parent / "tests" / src.stem


def build(src: Path) -> Path:
    if not src.exists():
        sys.exit(color(f"ファイルが見つかりません: {src}", RED))
    exe = exe_path(src)
    exe.parent.mkdir(parents=True, exist_ok=True)
    print(color(f"[ビルド] {src.relative_to(ROOT)}", CYAN), flush=True)
    result = subprocess.run([find_compiler(), str(src), "-o", str(exe), *CXXFLAGS])
    if result.returncode != 0:
        sys.exit(color("コンパイルエラー（CE）: 上のエラーメッセージを確認してください。", RED))
    return exe


def run(src: Path):
    exe = build(src)
    print(color("[実行] 入力があればキーボードから入力してください（終わりは Ctrl+Z → Enter）", CYAN))
    print("-" * 40, flush=True)
    code = subprocess.run([str(exe)]).returncode
    print("-" * 40, flush=True)
    if code != 0:
        print(color(f"終了コード {code}（実行時エラー RE の可能性があります）", RED))


def normalize(text: str):
    # 行末の空白と末尾の空行の違いは無視して比べる
    return [line.rstrip() for line in text.replace("\r\n", "\n").rstrip().split("\n")]


def test(src: Path) -> bool:
    cases = sorted(tests_dir(src).glob("*.in"), key=lambda p: (len(p.stem), p.stem))
    if not cases:
        print(color(f"入出力例がありません（{tests_dir(src).relative_to(ROOT)}）", YELLOW))
        return False
    exe = build(src)
    passed = 0
    for case in cases:
        expected_file = case.with_suffix(".out")
        input_text = case.read_text(encoding="utf-8")
        try:
            result = subprocess.run([str(exe)], input=input_text.encode("utf-8"),
                                    capture_output=True, timeout=TIME_LIMIT)
        except subprocess.TimeoutExpired:
            print(color(f"[TLE] 例{case.stem}: {TIME_LIMIT}秒以内に終わりませんでした", YELLOW))
            continue
        output = result.stdout.decode("utf-8", errors="replace")
        errors = result.stderr.decode("utf-8", errors="replace")
        if result.returncode != 0:
            status = color("[RE] ", RED)
        elif expected_file.exists() and normalize(output) == normalize(expected_file.read_text(encoding="utf-8")):
            print(color(f"[AC] 例{case.stem}", GREEN))
            passed += 1
            continue
        else:
            status = color("[WA] ", RED)
        print(status + f"例{case.stem}" + (f"（終了コード {result.returncode}）" if result.returncode else ""))
        print(color("  入力:", CYAN))
        print("    " + input_text.rstrip().replace("\n", "\n    "))
        if expected_file.exists():
            print(color("  正しい出力:", CYAN))
            print("    " + expected_file.read_text(encoding="utf-8").rstrip().replace("\n", "\n    "))
        print(color("  あなたの出力:", CYAN))
        print("    " + output.rstrip().replace("\n", "\n    "))
        if errors.strip():
            print(color("  エラー出力:", CYAN))
            print("    " + errors.rstrip().replace("\n", "\n    "))
    total = len(cases)
    ok = passed == total
    print(color(f"結果: {passed}/{total} 通過" + ("  すべて正解！提出してみましょう" if ok else ""),
                GREEN if ok else RED))
    return ok


def fetch_problem(task_id: str):
    req = urllib.request.Request(CONTEST_URL + task_id, headers={"User-Agent": "apg4b-helper"})
    with urllib.request.urlopen(req, timeout=10) as res:
        page = res.read().decode("utf-8")
    # 入出力例だけを取得する。ページ内のコードは完成した解答の可能性がある。
    problem = page.split("<h3>解答例", 1)[0]

    def samples(kind):
        found = re.findall(rf"<h3>{kind}\s*(\d+)</h3>\s*<pre>(.*?)</pre>", problem, re.S)
        return {n: html.unescape(body).replace("\r\n", "\n") for n, body in found}

    return samples("入力例"), samples("出力例")


def new(name: str):
    m = re.fullmatch(r"(?i)ex(\d+)", name)
    if not m or int(m.group(1)) not in EX_TASKS:
        sys.exit(color("EX1 〜 EX26 の形で指定してください（例: python tools/apg4b.py new EX5）", RED))
    num = int(m.group(1))
    task_id, chapter, folder = EX_TASKS[num]
    src = ROOT / folder / f"EX{num}.cpp"
    url = CONTEST_URL + task_id
    print(color(f"EX{num}（{chapter}）: {url}", CYAN))

    try:
        inputs, outputs = fetch_problem(task_id)
    except Exception as e:
        print(color(f"問題ページを取得できませんでした（{e}）。ひな形だけ作ります。", YELLOW))
        inputs, outputs = {}, {}

    src.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        print(f"{src.relative_to(ROOT)} はすでにあるので上書きしません")
    else:
        src.write_text(TEMPLATE, encoding="utf-8", newline="\n")
        print(f"作成: {src.relative_to(ROOT)}（空のひな形）")

    if inputs:
        tdir = tests_dir(src)
        tdir.mkdir(parents=True, exist_ok=True)
        for n, text in inputs.items():
            (tdir / f"{n}.in").write_text(text, encoding="utf-8", newline="\n")
            if n in outputs:
                (tdir / f"{n}.out").write_text(outputs[n], encoding="utf-8", newline="\n")
        print(f"入出力例を {len(inputs)} 個保存: {tdir.relative_to(ROOT)}")
    else:
        print("この問題には入力例がないので、実行して出力を目で確認してください")

    open_in_editor(src)


def open_in_editor(path: Path):
    """呼び出し元のエディタ（Zed / VS Code）でファイルを開く"""
    term = os.environ.get("TERM_PROGRAM", "").lower()
    if (term == "zed" or "ZED_TERM" in os.environ or "ZED_WORKTREE_ROOT" in os.environ) and shutil.which("zed"):
        cmd = ["zed", str(path)]
    elif term == "vscode" and shutil.which("code"):
        cmd = ["code", "-r", str(path)]
    else:
        return
    subprocess.run(cmd, shell=(sys.platform == "win32"))


def main():
    use_utf8_console()
    parser = argparse.ArgumentParser(description="APG4b 学習用ヘルパー")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new", help="問題を準備する").add_argument("name", nargs="?", help="EX1 〜 EX26")
    for cmd in ("build", "run", "test", "auto"):
        sub.add_parser(cmd).add_argument("file", help=".cpp ファイル")
    args = parser.parse_args()

    if args.cmd == "new":
        # 番号を省略したらその場で聞く（Zed のタスクから使うため）
        new(args.name or input("EX番号を入力してください（例: EX4）: ").strip())
        return
    src = Path(args.file).resolve()
    if src.suffix != ".cpp":
        sys.exit(color(".cpp ファイルを開いた状態で実行してください", RED))
    if args.cmd == "build":
        build(src)
        print(color("ビルド成功", GREEN))
    elif args.cmd == "run":
        run(src)
    elif args.cmd == "test":
        sys.exit(0 if test(src) else 1)
    elif args.cmd == "auto":
        if any(tests_dir(src).glob("*.in")):
            sys.exit(0 if test(src) else 1)
        run(src)


if __name__ == "__main__":
    main()
