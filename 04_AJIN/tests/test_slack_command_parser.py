"""v4.7 C-3 — Slack 슬래시 명령어 파서 단위 테스트."""

from backend.services.slack.command_parser import parse_command


def test_ask_simple():
    c = parse_command("ask 8D 절차 알려줘")
    assert c.kind == "ask"
    assert c.query == "8D 절차 알려줘"
    assert c.department is None


def test_ask_with_dept_space():
    c = parse_command("ask --dept HR 휴가 신청")
    assert c.kind == "ask"
    assert c.query == "휴가 신청"
    assert c.department == "HR"


def test_ask_with_dept_equals():
    c = parse_command("ask --dept=QA SPC 절차")
    assert c.kind == "ask"
    assert c.query == "SPC 절차"
    assert c.department == "QA"


def test_help():
    c = parse_command("help")
    assert c.kind == "help"


def test_empty():
    assert parse_command("").kind == "unknown"
    assert parse_command("   ").kind == "unknown"


def test_unknown():
    assert parse_command("foobar").kind == "unknown"


def test_ask_no_query():
    assert parse_command("ask").kind == "unknown"
    assert parse_command("ask --dept HR").kind == "unknown"
