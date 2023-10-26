from dataclasses import dataclass
from typing import Callable

from parsy import OUT, Parser, ParseState, Result, regex, success, whitespace


@dataclass
class State:
    state: ParseState

    def apply(self, parser: Parser[OUT]) -> OUT:
        result, self.state = parser.parse_state(self.state)
        return result

    def success(self, value: OUT) -> Result[OUT]:
        return Result.success(self.state.index, value)


@dataclass
class Person:
    name: str
    age: int
    note: str


def stateful_parser(fn: Callable[[State], Result[OUT]]) -> Parser[OUT]:
    @Parser
    def the_parser(parse_state: ParseState) -> Result[OUT]:
        state = State(parse_state)
        return fn(state)

    return the_parser


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

    result = person_parser.parse("Rob 29 note")
    assert result == Person("Rob", 29, "Odd age")


def test_stateful_parser_without_mutation():
    @Parser
    def alternative(s: ParseState) -> Result[Person]:

        name, s = s.apply(regex(r"\w+") << whitespace)
        age, s = s.apply((regex(r"\d+") << whitespace).map(int))

        if age % 2:
            # Parsing depends on previously parsed values
            note, s = s.apply(regex(".+") >> success("Odd age"))
        else:
            note, s = s.apply(regex(".+"))

        return Result.success(s.index, Person(name, age, note))

    result = alternative.parse("Rob 29 note")
    assert result == Person("Rob", 29, "Odd age")
