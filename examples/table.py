from typing import Dict, List

from parsy import Parser, Result, State, regex, stateful_parser, string


@stateful_parser
def header_parser(state: State) -> Result[List[str]]:
    headers = state.apply(regex(r"[^,\n]*").sep_by(string(",")) << string("\n"))
    return state.success(headers)


def row_parser(headers: List[str]) -> Parser[Dict[str, str]]:
    @stateful_parser
    def parser(state: State) -> Result[Dict[str, str]]:
        values = state.apply(
            regex(r"[^,\n]*").sep_by(string(","), min=len(headers), max=len(headers))
            << string("\n").optional()
        )
        return state.success(dict(zip(headers, values)))

    return parser


@stateful_parser
def table_parser(state: State) -> Result[List[Dict[str, str]]]:
    headers = state.apply(header_parser)
    rows = state.apply(row_parser(headers).many())
    return state.success(rows)


def test_table_parser() -> None:
    table = """
name,age,city
Alice,20,London
Bob,30,Edinburgh
Charlie,40,Dunstable
    """.strip()

    parsed_table = table_parser.parse(table)

    expected_table = [
        {"name": "Alice", "age": "20", "city": "London"},
        {"name": "Bob", "age": "30", "city": "Edinburgh"},
        {"name": "Charlie", "age": "40", "city": "Dunstable"},
    ]

    assert (
        parsed_table == expected_table
    ), f"Expected {expected_table}, but got {parsed_table}"
