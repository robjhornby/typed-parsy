"""
Debugging most combined parsers is difficult in Parsy, apart from `@generate` parsers
because you can easily set a breakpoint somewhere where the text being parsed and its
intermediate results are visible.
`@generate` can't be type annotated because the Python type system requires all
yield and send types to be homogeneous in a generator (i.e. you can yield a string
parser and yield a bool parser in a single @generate parser in a type-safe way).

Stateful parsers are an attempt at an alternative syntax. Instead of `yield parser`,
it's do `state.apply(parser)`. The state of the parser is available in debugging
(input text, index, and any results already parsed in the current parser).
"""
from dataclasses import dataclass

import pytest

from parsy import ParseError, Result, State, regex, stateful_parser, success, whitespace


@dataclass
class Person:
    name: str
    age: int
    note: str


def test_stateful_parser() -> None:
    @stateful_parser
    def person_parser(state: State) -> Result[Person]:
        name = state.apply(regex(r"\w+") << whitespace)
        age = state.apply((regex(r"\d+") << whitespace).map(int))

        # Example: setting a breakpoint here, we'll see the parsed values for name and
        # age in a debugger, and `state` will contain the input text and current index

        if age % 2:
            # Parsing depends on previously parsed values
            note = state.apply(regex(".+") >> success("Odd age"))
        else:
            note = state.apply(regex(".+"))

        return state.success(Person(name, age, note))

    result = person_parser.parse("Frodo 29 note")
    assert result == Person("Frodo", 29, "Odd age")


def test_stateful_parser_failure() -> None:
    @stateful_parser
    def person(s: State) -> Result[Person]:
        name = s.apply(regex(r"\w+") << whitespace)
        age = s.apply((regex(r"\d+") << whitespace).map(int).desc("digit"))

        return s.success(Person(name, age, "default"))

    with pytest.raises(ParseError) as exception:
        person.parse("Frodo what")

    # Parsing fails part way through
    assert exception.value.state.index == 6
    # Parsing fails on the digit regex parser
    assert exception.value.expected == {"digit"}
