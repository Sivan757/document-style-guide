#!/usr/bin/env python3
"""机械检查《中文技术文档的写作规范》中可以判定的规则。

用法：
    python3 check_style.py FILE_OR_DIR [...]
    python3 check_style.py . --json

退出码：0 表示没有 error（warning 不影响），1 表示存在 error。
规则编号对应 references/ 下的小节。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CJK = r"\u4e00-\u9fff"
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdx"}
ALLOWED_UPPER_NAMES = {"README.md", "LICENSE", "CHANGELOG.md", "LICENSE.md", "SKILL.md", "AGENTS.md"}
INLINE_CODE = re.compile(r"`[^`]*`")
LINK_TARGET = re.compile(r"\]\([^)]*\)")
URL = re.compile(r"https?://\S+")
FENCE = re.compile(r"^\s*(```|~~~)")

RULES = {
    "fullwidth-digit": ("error", "数值使用半角数字（number.md）"),
    "cjk-ascii-space": ("warning", "中文与半角英文字符之间应有一个半角空格（text.md）"),
    "cjk-digit-space": ("warning", "同一文档中中文与数字的空格风格不一致（text.md）"),
    "halfwidth-in-cjk": ("warning", "中文语句应使用全角标点（marks.md）"),
    "bracket-space": ("warning", "全角标点前后不留空格（text.md）"),
    "exclaim-repeat": ("error", "感叹号不得连用（marks.md）"),
    "ellipsis": ("warning", "省略号应使用 ⋯⋯（marks.md）"),
    "ellipsis-with-deng": ("warning", "省略号不与“等”同时使用（marks.md）"),
    "heading-jump": ("error", "标题层级不得跳级（title.md）"),
    "heading-punct": ("warning", "点号不得出现在标题末尾（marks.md）"),
    "line-start-punct": ("error", "点号不得出现在行首（marks.md）"),
    "reduced-times": ("error", "不写“降低 N 倍”“减少 N 倍”（number.md）"),
    "thousands": ("info", "四位以上数值加千分号（number.md）"),
    "indent": ("info", "段落开头不留空白字符（paragraph.md）"),
    "filename": ("warning", "文件名用半角小写与连字符（structure.md）"),
}


class Finding:
    __slots__ = ("path", "line", "rule", "severity", "message", "excerpt")

    def __init__(self, path: Path, line: int, rule: str, excerpt: str) -> None:
        severity, message = RULES[rule]
        self.path, self.line, self.rule = path, line, rule
        self.severity, self.message, self.excerpt = severity, message, excerpt

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "line": self.line,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "excerpt": self.excerpt,
        }

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.severity} [{self.rule}] {self.message}\n    {self.excerpt}"


def strip_non_prose(line: str) -> str:
    """去掉行内代码、链接目标与网址，避免误报。"""
    line = INLINE_CODE.sub("\u0000", line)
    line = LINK_TARGET.sub("]", line)
    return URL.sub("\u0000", line)


def check_line(line: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if re.search(r"[０-９]", line):
        hits.append(("fullwidth-digit", "全角数字"))
    if re.search(rf"[{CJK}][A-Za-z]", line) or re.search(rf"[A-Za-z][{CJK}]", line):
        hits.append(("cjk-ascii-space", "中文与英文紧贴"))
    if re.search(rf"[{CJK}][0-9]", line) or re.search(rf"[0-9][{CJK}]", line):
        hits.append(("cjk-digit-space", "中文与数字紧贴"))
    if re.search(rf"[{CJK}][,;:?!]", line) or re.search(rf"[,;:?!][{CJK}]", line):
        hits.append(("halfwidth-in-cjk", "半角标点混入中文"))
    if re.search(rf"[{CJK}]\s*,\s*[{CJK}]", line):
        hits.append(("halfwidth-in-cjk", "并列词应使用顿号"))
    if re.search(r"[ \t]+[，。、；：！？（）“”《》]", line):
        hits.append(("bracket-space", "全角标点前有空格"))
    if re.search(r"！{2,}|!{2,}", line):
        hits.append(("exclaim-repeat", "感叹号连用"))
    if re.search(rf"[{CJK}]{{0,4}}(。。。|\.\.\.)(?![\w/])", line):
        hits.append(("ellipsis", "非标准省略号"))
    if re.search(r"…(?![…])", line) or re.search(r"……", line):
        hits.append(("ellipsis", "省略号应写成 ⋯⋯"))
    if re.search(r"(⋯⋯|…|\.\.\.)\s*等", line):
        hits.append(("ellipsis-with-deng", "省略号与“等”并用"))
    if re.search(r"(降低|减少|下降|缩短|缩减)(了|到)?\s*[0-9０-９一二三四五六七八九十百几]+\s*倍", line):
        hits.append(("reduced-times", "降低/减少 N 倍"))
    if re.search(r"(?<![\d,.])\d{5,}(?![\d,.])", line):
        hits.append(("thousands", "五位以上数字缺千分号"))
    if re.match(r"^\s*[,，。、；：!?！？]", line):
        hits.append(("line-start-punct", "行首标点"))
    if re.match(r"^[\u3000]+\S", line):
        hits.append(("indent", "段落开头有空白字符"))
    return hits


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    fenced = False
    previous_level = 0
    digit_findings: list[Finding] = []
    spaced_digit = False
    for number, raw in enumerate(text.splitlines(), start=1):
        if FENCE.match(raw):
            fenced = not fenced
            continue
        if fenced:
            continue

        heading = re.match(r"^(#{1,6})\s+(.*?)\s*$", raw)
        if heading:
            level = len(heading.group(1))
            if previous_level and level > previous_level + 1:
                findings.append(Finding(path, number, "heading-jump", raw.strip()))
            previous_level = level
            if re.search(r"[。，、；：.,;:]$", heading.group(2)):
                findings.append(Finding(path, number, "heading-punct", raw.strip()))

        prose = strip_non_prose(raw)
        if re.search(rf"[{CJK}] [0-9]", prose) or re.search(rf"[0-9] [{CJK}]", prose):
            spaced_digit = True
        for rule, excerpt in check_line(prose):
            finding = Finding(path, number, rule, excerpt + "：" + raw.strip())
            if rule == "cjk-digit-space":
                digit_findings.append(finding)
            else:
                findings.append(finding)

    # 中文与数字之间的空格可有可无，但同一文档必须统一，只有混杂时才报告。
    if spaced_digit:
        findings.extend(digit_findings)

    return findings


def scan_paths(targets: list[Path]) -> list[Finding]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(p for p in sorted(target.rglob("*")) if p.is_file())
        elif target.is_file():
            files.append(target)
        else:
            print(f"跳过不存在的路径：{target}", file=sys.stderr)

    findings: list[Finding] = []
    for path in files:
        if path.suffix.lower() in MARKDOWN_SUFFIXES:
            findings.extend(scan_file(path))
        bad_name = re.search(r"[\s_\u4e00-\u9fff]", path.name) or path.stem != path.stem.lower()
        if bad_name and path.name not in ALLOWED_UPPER_NAMES:
            findings.append(Finding(path, 0, "filename", str(path.name)))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="检查中文技术文档的机械规则")
    parser.add_argument("targets", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--max", type=int, default=200, help="最多报告的条目数")
    args = parser.parse_args()

    findings = scan_paths(args.targets)
    shown = findings[: args.max]

    if args.json:
        print(json.dumps(
            {"count": len(findings), "findings": [f.as_dict() for f in shown]},
            ensure_ascii=False,
            indent=2,
        ))
    else:
        for finding in shown:
            print(finding.format())
        if len(findings) > len(shown):
            print(f"…还有 {len(findings) - len(shown)} 条未显示")
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        infos = sum(1 for f in findings if f.severity == "info")
        print(f"\n共 {len(findings)} 条：error {errors}，warning {warnings}，info {infos}")

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
