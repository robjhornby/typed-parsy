from dataclasses import dataclass

from parsy import OUT, Parser, ParseState, Result, regex, success, whitespace


@dataclass
class State:
    state: ParseState

    def apply(self, parser: Parser[OUT]) -> OUT:
        result, self.state = parser.parse_state(self.state)
        return result

    @staticmethod
    def start(state: ParseState):
        return State(state)

    def success(self, value: OUT) -> Result[OUT]:
        return Result.success(self.state.index, value)


@dataclass
class Person:
    name: str
    age: int
    note: str


@Parser
def person_parser(parse_state: ParseState) -> Result[Person]:
    state = State.start(parse_state)
    name = state.apply(regex(r"\w+") << whitespace)

    # But every parser starts by matching a string anyway: other types only come
    # from further function logic, which doesn't need to be part of the parser when
    # using a generator:
    age = state.apply((regex(r"\d+") << whitespace).map(int))

    if age % 2:
        # Parsing depends on previously parsed values
        note = state.apply(regex(".+") >> success("Odd age"))
    else:
        note = state.apply(regex(".+"))

    return state.success(Person(name, age, note))


result = person_parser.parse("Rob 29 note")
print(result)
