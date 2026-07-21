#!/usr/bin/env python3
"""Deterministic format and listening-readability checks for Chinese transcripts."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path


SECTION_RE = re.compile(r"^第[一二三四五六七八九十百]+部分$")
SENTENCE_RE = re.compile(r"[^。！？!?]+[。！？!?]?")
MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)", re.MULTILINE)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
CITATION_RE = re.compile(r"(?:\[\d+\]|【\d+】|（?来源[:：]|参考资料|资料来源)")
PLACEHOLDER_RE = re.compile(
    r"(?:TODO|TBD|待补充|待核实|待确认|N\s*倍|XX+|\[在此|\{\{.+?\}\})",
    re.IGNORECASE,
)
DECORATIVE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|={3,}|_{3,}|—{4,})\s*$", re.MULTILINE)
EMOJI_RE = re.compile("[\U0001f000-\U0001faff\U00002600-\U000027bf]")
FAKE_IDENTITY_RE = re.compile(r"欢迎[^。]{0,30}[，,]\s*我是[^，。]{1,20}[，。]")
META_RE = re.compile(
    r"^(?:以下是|下面是|下面为你|这是为你生成的|创作说明|写作说明|评分结果|事实底稿)",
    re.MULTILINE,
)

ORAL_MARKERS = (
    "我们",
    "你会发现",
    "你可能",
    "换句话说",
    "也就是说",
    "简单来说",
    "说到这里",
    "接下来",
    "那么",
    "所以",
    "不过",
    "但是",
    "其实",
    "比如",
    "最后",
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str


def visible_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--min-chars", type=int, default=6900)
    parser.add_argument("--max-chars", type=int, default=10600)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def analyze_text(
    text: str,
    *,
    title: str | None = None,
    min_chars: int = 6900,
    max_chars: int = 10600,
) -> dict[str, object]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    issues: list[Issue] = []

    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()
    ]
    prose_paragraphs = [part for part in paragraphs if not SECTION_RE.fullmatch(part)]
    section_headings = [part for part in paragraphs if SECTION_RE.fullmatch(part)]
    sentences = [
        part.strip() for part in SENTENCE_RE.findall(normalized) if part.strip()
    ]
    sentence_lengths = [visible_length(part) for part in sentences]
    paragraph_lengths = [visible_length(part) for part in prose_paragraphs]
    characters = visible_length(normalized)

    def add(severity: str, code: str, message: str) -> None:
        issues.append(Issue(severity, code, message))

    if not normalized:
        add("error", "empty", "逐字稿为空。")
    if characters < min_chars:
        add("error", "too_short", f"非空白字符 {characters}，少于下限 {min_chars}。")
    if characters > max_chars:
        add("error", "too_long", f"非空白字符 {characters}，超过上限 {max_chars}。")

    if not re.match(r"^你好[，,]?\s*欢迎(?:你)?每天听本书", normalized):
        add("error", "opening", "正文没有从“你好，欢迎每天听本书”式问候直接开始。")
    if title:
        clean_title = title.strip().strip("《》")
        opening = normalized[:600]
        if clean_title not in opening:
            add("error", "title_missing", f"开场 600 字内没有出现书名“{clean_title}”。")

    if len(section_headings) < 2 or len(section_headings) > 4:
        add(
            "warning",
            "section_count",
            f"检测到 {len(section_headings)} 个主体部分，建议使用 2 至 4 个。",
        )
    if len(paragraphs) < 32:
        add(
            "warning",
            "few_paragraphs",
            f"仅 {len(paragraphs)} 个段落，长篇听感可能过于拥挤。",
        )
    if len(paragraphs) > 110:
        add(
            "warning",
            "many_paragraphs",
            f"共有 {len(paragraphs)} 个段落，可能过于碎片化。",
        )

    forbidden_checks = (
        (MARKDOWN_HEADING_RE, "markdown_heading", "出现 Markdown 标题。"),
        (BULLET_RE, "bullet_list", "出现项目符号或编号列表。"),
        (URL_RE, "url", "出现网址。"),
        (CITATION_RE, "citation", "出现引用编号、来源标题或参考资料。"),
        (PLACEHOLDER_RE, "placeholder", "出现占位符或待核实文本。"),
        (DECORATIVE_RE, "decorative_separator", "出现装饰分隔线。"),
        (EMOJI_RE, "emoji", "出现 Emoji 或装饰图形。"),
        (META_RE, "meta_text", "出现正文之外的创作或交付说明。"),
    )
    for pattern, code, message in forbidden_checks:
        if pattern.search(normalized):
            add("error", code, message)

    if "```" in normalized or "`" in normalized:
        add("error", "code_markup", "出现代码块或反引号。")
    if "|" in normalized:
        add("error", "table_pipe", "出现可能属于表格的竖线。")
    if FAKE_IDENTITY_RE.search(normalized[:500]):
        add("error", "fake_identity", "开场出现未经用户提供的主播身份。")

    repeated = sorted(
        {part for part in prose_paragraphs if prose_paragraphs.count(part) > 1}
    )
    if repeated:
        add("error", "duplicate_paragraph", f"发现 {len(repeated)} 个完全重复段落。")

    if sentence_lengths:
        mean_sentence = statistics.mean(sentence_lengths)
        median_sentence = statistics.median(sentence_lengths)
        max_sentence = max(sentence_lengths)
        if mean_sentence < 29 or mean_sentence > 52:
            add(
                "warning",
                "sentence_mean",
                f"平均句长 {mean_sentence:.1f}，建议约 30 至 50。",
            )
        if max_sentence > 220:
            add(
                "warning",
                "very_long_sentence",
                f"最长句 {max_sentence} 字，朗读时可能难以跟随。",
            )
    else:
        mean_sentence = 0.0
        median_sentence = 0.0
        max_sentence = 0

    long_paragraphs = sum(length > 360 for length in paragraph_lengths)
    if long_paragraphs:
        add("warning", "long_paragraphs", f"有 {long_paragraphs} 个段落超过 360 字。")

    oral_hits = sum(normalized.count(marker) for marker in ORAL_MARKERS)
    oral_rate = oral_hits / characters * 1000 if characters else 0.0
    if oral_rate < 5.5:
        add(
            "warning",
            "few_oral_markers",
            f"口语导航词每千字 {oral_rate:.2f} 次，低于建议值 5.5，可能偏书面。",
        )
    if oral_rate > 18:
        add(
            "warning",
            "many_oral_markers",
            f"口语导航词每千字 {oral_rate:.2f} 次，检查是否机械重复。",
        )

    questions = normalized.count("？") + normalized.count("?")
    exclamations = normalized.count("！") + normalized.count("!")
    if questions < 3:
        add("warning", "few_questions", "疑问句少于 3 个，检查是否缺少真实的问题牵引。")
    if exclamations > 8:
        add(
            "warning",
            "many_exclamations",
            f"感叹号达到 {exclamations} 个，语气可能过度夸张。",
        )

    if normalized and normalized[-1] not in '。！？!?"”’』」》':
        add("warning", "unfinished_ending", "正文末尾不像完整句子。")

    metrics = {
        "non_whitespace_characters": characters,
        "paragraphs": len(paragraphs),
        "prose_paragraphs": len(prose_paragraphs),
        "sections": len(section_headings),
        "section_headings": section_headings,
        "sentences": len(sentences),
        "mean_sentence_length": round(mean_sentence, 2),
        "median_sentence_length": round(median_sentence, 2),
        "max_sentence_length": max_sentence,
        "mean_paragraph_length": round(statistics.mean(paragraph_lengths), 2)
        if paragraph_lengths
        else 0.0,
        "median_paragraph_length": round(statistics.median(paragraph_lengths), 2)
        if paragraph_lengths
        else 0.0,
        "long_paragraphs": long_paragraphs,
        "oral_marker_hits": oral_hits,
        "oral_marker_rate_per_1000": round(oral_rate, 2),
        "questions": questions,
        "exclamations": exclamations,
    }
    return {
        "passed": not any(issue.severity == "error" for issue in issues),
        "metrics": metrics,
        "issues": [asdict(issue) for issue in issues],
    }


def main() -> None:
    args = parse_args()
    text = args.transcript.read_text(encoding="utf-8-sig")
    result = analyze_text(
        text,
        title=args.title,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status}: {args.transcript}")
        print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
        for issue in result["issues"]:
            print(f"[{issue['severity'].upper()}] {issue['code']}: {issue['message']}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
