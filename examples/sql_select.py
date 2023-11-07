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

from parsy import from_enum, gather, regex, string, take


class Operator(enum.Enum):
    EQ = "="
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="


identifier = regex("[a-zA-Z][a-zA-Z0-9_]*")


space = regex(r"\s+")  # non-optional whitespace
padding = regex(r"\s*")  # optional whitespace

operator = from_enum(Operator)


@dataclass
class Number:
    value: int = take(regex(r"-?[0-9]+").map(int))


@dataclass
class String:
    value: str = take(regex(r"'([^']*)'", group=1))


@dataclass
class Field:
    name: str = take(identifier)


@dataclass
class Table:
    name: str = take(identifier)


ColumnExpression = Union[Field, String, Number]

column_expr = gather(Field) | gather(String) | gather(Number)


@dataclass
class Comparison:
    left: ColumnExpression = take(column_expr << padding)
    operator: Operator = take(operator)
    right: ColumnExpression = take(padding >> column_expr)


SELECT = string("SELECT") << space
FROM = space >> string("FROM") << space
WHERE = space >> string("WHERE") << space


@dataclass
class Select:
    columns: List[ColumnExpression] = take(SELECT >> column_expr.sep_by(padding + string(",") + padding, min=1))
    table: Table = take(FROM >> gather(Table))
    where: Optional[Comparison] = take((WHERE >> gather(Comparison)).optional() << (padding + string(";")))


select = gather(Select)


def test_select() -> None:
    assert select.parse("SELECT thing, stuff, 123, 'hello' FROM my_table WHERE id = 1;") == Select(
        columns=[Field("thing"), Field("stuff"), Number(123), String("hello")],
        table=Table("my_table"),
        where=Comparison(left=Field("id"), operator=Operator.EQ, right=Number(1)),
    )


def test_optional_where() -> None:
    assert select.parse("SELECT 1 FROM x;") == Select(
        columns=[Number(1)],
        table=Table("x"),
        where=None,
    )
