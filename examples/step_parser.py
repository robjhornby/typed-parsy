from dataclasses import dataclass

import pytest

from parsy import ParseError, Result, State, regex, stateful_parser, success, whitespace


@dataclass
class Person:
    name: str
    age: int
    note: str


def test_stateful_parser():
    @stateful_parser
    def person_parser(state: State) -> Result[Person]:

        name = state.apply(regex(r"\w+") << whitespace)
        age = state.apply((regex(r"\d+") << whitespace).map(int))

        if age % 2:
            # Parsing depends on previously parsed values
            note = state.apply(regex(".+") >> success("Odd age"))
        else:
            note = state.apply(regex(".+"))

        return state.success(Person(name, age, note))

    result = person_parser.parse("Frodo 29 note")
    assert result == Person("Frodo", 29, "Odd age")


def test_stateful_parser_failure():
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
