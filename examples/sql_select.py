# A very limited parser for SQL SELECT statements,
# for demo purposes. Supports:
# 1. A simple list of columns (or number/string literals)
# 2. A simple table name
# 3. An optional where condition,
#    which has the form of 'A op B' where A and B are columns, strings or number,
#    and op is a comparison operator
#
# We demonstrate the use of `map` to create AST nodes with a single arg,
# and `seq` for AST nodes with more than one arg.

import enum
from dataclasses import dataclass
from typing import List, Optional, Union

from parsy import from_enum, regex, seq, string

# -- AST nodes:


class Operator(enum.Enum):
    EQ = "="
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="


@dataclass
class Number:
    value: int


@dataclass
class String:
    value: str


@dataclass
class Field:
    name: str


@dataclass
class Table:
    name: str


ColumnExpression = Union[Field, String, Number]


@dataclass
class Comparison:
    left: ColumnExpression
    operator: Operator
    right: ColumnExpression


@dataclass
class Select:
    columns: List[ColumnExpression]
    table: Table
    where: Optional[Comparison]


# -- Parsers:

number_literal = regex(r"-?[0-9]+").map(int).map(Number)

# We don't support ' in strings or escaping for simplicity
string_literal = regex(r"'([^']*)'", group=1).map(String)

identifier = regex("[a-zA-Z][a-zA-Z0-9_]*")

field = identifier.map(Field)

table = identifier.map(Table)

space = regex(r"\s+")  # non-optional whitespace
padding = regex(r"\s*")  # optional whitespace

column_expr = field | string_literal | number_literal

operator = from_enum(Operator)

comparison = seq((column_expr << padding), operator, (padding >> column_expr)).combine(Comparison)


SELECT = string("SELECT") << space
FROM = space >> string("FROM") << space
WHERE = space >> string("WHERE") << space

select = seq(
    SELECT >> column_expr.sep_by(padding + string(",") + padding, min=1),
    FROM >> table,
    (WHERE >> comparison).optional() << (padding + string(";")),
).combine(Select)


# Run these tests with pytest:


def test_select():
    assert select.parse("SELECT thing, stuff, 123, 'hello' FROM my_table WHERE id = 1;") == Select(
        columns=[Field("thing"), Field("stuff"), Number(123), String("hello")],
        table=Table("my_table"),
        where=Comparison(left=Field("id"), operator=Operator.EQ, right=Number(1)),
    )


def test_optional_where():
    assert select.parse("SELECT 1 FROM x;") == Select(
        columns=[Number(1)],
        table=Table("x"),
        where=None,
    )
