from typing import Dict, Iterator, List, TypeVar, Union

from parsy import Parser, forward_parser, regex, string

# Utilities
whitespace = regex(r"\s*")

T = TypeVar("T")


def lexeme(p: Parser[T]) -> Parser[T]:
    return p << whitespace


# Punctuation
lbrace = lexeme(string("{"))
rbrace = lexeme(string("}"))
lbrack = lexeme(string("["))
rbrack = lexeme(string("]"))
colon = lexeme(string(":"))
comma = lexeme(string(","))

# Primitives
true = lexeme(string("true")).result(True)
false = lexeme(string("false")).result(False)
null = lexeme(string("null")).result(None)
number = lexeme(regex(r"-?(0|[1-9][0-9]*)([.][0-9]+)?([eE][+-]?[0-9]+)?")).map(float)
string_part = regex(r'[^"\\]+')
string_esc = string("\\") >> (
    string("\\")
    | string("/")
    | string('"')
    | string("b").result("\b")
    | string("f").result("\f")
    | string("n").result("\n")
    | string("r").result("\r")
    | string("t").result("\t")
    | regex(r"u([0-9a-fA-F]{4})", group=1).map(lambda s: chr(int(s, 16)))
)
quoted = lexeme(
    string('"') >> (string_part | string_esc).many().concat() << string('"')
)

# Data structures
JSON = Union[Dict[str, "JSON"], List["JSON"], str, float, bool, None]


@forward_parser
def _json_parser() -> Iterator[Parser[JSON]]:
    yield json_parser


object_pair = (quoted << colon) & _json_parser
prs = object_pair.sep_by(comma)
json_object = lbrace >> object_pair.sep_by(comma).map(dict) << rbrace
array = lbrack >> _json_parser.sep_by(comma) << rbrack

# Everything
json_parser = quoted | number | json_object | array | true | false | null

json_doc = whitespace >> json_parser


def test_json_parser() -> None:
    result = json_doc.parse(
        r"""
    {
        "int": 1,
        "string": "hello",
        "a list": [1, 2, 3],
        "escapes": "\n \u24D2",
        "nested": {"x": "y"},
        "other": [true, false, null]
    }
    """
    )

    assert result == {
        "int": 1,
        "string": "hello",
        "a list": [1, 2, 3],
        "escapes": "\n ⓒ",
        "nested": {"x": "y"},
        "other": [True, False, None],
    }
