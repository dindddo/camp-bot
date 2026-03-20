from __future__ import annotations

import os
import re
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Day 번호 → 템플릿 파일 매핑
DAY_TEMPLATES = {
    1: "day1_assignment.txt",
    2: "day2_assignment.txt",
    3: "day3_assignment.txt",
    4: "day4_assignment.txt",
    5: "day5_assignment.txt",
}


def get_day_template(day: int) -> str | None:
    """Day 번호에 해당하는 템플릿 내용을 반환합니다."""
    filename = DAY_TEMPLATES.get(day)
    if not filename:
        return None
    filepath = TEMPLATE_DIR / filename
    if not filepath.exists():
        return None
    return filepath.read_text(encoding="utf-8")


def get_available_days() -> list[int]:
    """템플릿이 존재하는 Day 목록을 반환합니다."""
    available = []
    for day, filename in DAY_TEMPLATES.items():
        if (TEMPLATE_DIR / filename).exists():
            available.append(day)
    return sorted(available)


def parse_day_number(text: str) -> int | None:
    """텍스트에서 Day 번호를 추출합니다.

    'day1', 'day 1', 'Day1', 'd1', '1' 등을 인식합니다.
    """
    text = text.strip().lower()
    match = re.match(r"^(?:day\s*|d)(\d+)$", text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    return None
