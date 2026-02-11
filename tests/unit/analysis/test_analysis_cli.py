from __future__ import annotations

from merit.cli import _build_parser


def test_build_parser_registers_analyze_errors_command() -> None:
    parser = _build_parser()
    args = parser.parse_args(["analyze", "errors"])

    assert args.command == "analyze"
    assert args.analysis_type == "errors"
    assert hasattr(args, "func")
