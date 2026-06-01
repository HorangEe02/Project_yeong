"""v4.7 C-3 — `/ajin <subcommand> ...` 슬래시 명령어 문법 파싱.

지원 문법:
  ask <query>                  → SlackCommand(kind='ask', query=..., department=None)
  ask --dept <NAME> <query>    → SlackCommand(kind='ask', query=..., department=NAME)
  help                         → SlackCommand(kind='help')
  (그 외 / 빈 값)              → SlackCommand(kind='unknown')
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Literal


CommandKind = Literal["ask", "help", "unknown"]


@dataclass(frozen=True)
class SlackCommand:
    kind: CommandKind
    query: str = ""
    department: str | None = None


_DEPT_FLAG_RE = re.compile(r"^--dept(?:=(\S+))?$")


def parse_command(text: str) -> SlackCommand:
    """Slack `text` payload(슬래시 명령어 뒤 본문) 파싱.

    Examples:
        parse_command('ask 8D 절차')                       → ask, q='8D 절차'
        parse_command('ask --dept HR 휴가 신청 방법')        → ask, q='휴가 신청 방법', dept='HR'
        parse_command('help')                              → help
        parse_command('')                                  → unknown
    """
    if not text:
        return SlackCommand(kind="unknown")

    s = text.strip()
    if not s:
        return SlackCommand(kind="unknown")

    # 1) help
    if s.lower() == "help":
        return SlackCommand(kind="help")

    # 2) ask
    try:
        # 따옴표가 있을 수 있으니 shlex (자동차 부품 한글 텍스트는 그대로 통과)
        tokens = shlex.split(s, posix=True)
    except ValueError:
        tokens = s.split()

    if not tokens or tokens[0].lower() != "ask":
        return SlackCommand(kind="unknown")

    rest = tokens[1:]
    if not rest:
        return SlackCommand(kind="unknown")

    department: str | None = None
    # --dept HR / --dept=HR 둘 다 허용
    if rest:
        m = _DEPT_FLAG_RE.match(rest[0])
        if m:
            if m.group(1):
                department = m.group(1)
                rest = rest[1:]
            else:
                # `--dept HR` 형태 — 다음 토큰이 값
                if len(rest) >= 2:
                    department = rest[1]
                    rest = rest[2:]
                else:
                    rest = rest[1:]

    query = " ".join(rest).strip()
    if not query:
        return SlackCommand(kind="unknown")

    return SlackCommand(kind="ask", query=query, department=department)
