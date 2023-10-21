# End-user documentation is in ../../doc/ and so is for the most part not
# duplicated here in the form of doc strings. Code comments and docstrings
# are mainly for internal use.
from __future__ import annotations

import enum
import operator
import re
from dataclasses import Field, dataclass, field, fields
from functools import reduce, wraps
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    Generator,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import Literal, ParamSpec, Protocol, TypeGuard, TypeVarTuple, Unpack

OUT = TypeVar("OUT")
OUT1 = TypeVar("OUT1")
OUT2 = TypeVar("OUT2")
OUT3 = TypeVar("OUT3")
OUT4 = TypeVar("OUT4")
OUT5 = TypeVar("OUT5")
OUT6 = TypeVar("OUT6")
OUT_T = TypeVarTuple("OUT_T")
OUT_T2 = TypeVarTuple("OUT_T2")
OUT_co = TypeVar("OUT_co", covariant=True)
OUT2_co = TypeVar("OUT2_co", covariant=True)

P = ParamSpec("P")

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

_T_contra = TypeVar("_T_contra", contravariant=True)

_T_co = TypeVar("_T_co", covariant=True)

TUPLE_T = TypeVar("TUPLE_T")
TUP1 = Tuple[TUPLE_T]
TUP2 = Tuple[TUPLE_T, TUPLE_T]
TUP3 = Tuple[TUPLE_T, TUPLE_T, TUPLE_T]
TUP4 = Tuple[TUPLE_T, TUPLE_T, TUPLE_T, TUPLE_T]
TUP5 = Tuple[TUPLE_T, TUPLE_T, TUPLE_T, TUPLE_T, TUPLE_T]
TUP6 = Tuple[TUPLE_T, TUPLE_T, TUPLE_T, TUPLE_T, TUPLE_T, TUPLE_T]


class SupportsAdd(Protocol[_T_contra, _T_co]):
    def __add__(self, __x: _T_contra) -> _T_co:
        ...


def noop(val: T) -> T:
    return val


@dataclass(frozen=True)
class ParseState:
    stream: str
    index: int

    @staticmethod
    def start(stream: str) -> ParseState:
        return ParseState(stream, 0)

    def at(self: ParseState, index: int) -> ParseState:
        return ParseState(self.stream, index)

    def apply(self, parser: Parser[OUT]) -> Tuple[OUT, ParseState]:
        return parser.parse_state(self)

    def success(self, value: OUT) -> Result[OUT]:
        return Result.success(self.index, value)


def line_info_at(state: ParseState) -> Tuple[int, int]:
    if state.index > len(state.stream):
        raise ValueError("invalid state.index")
    line = state.stream.count("\n", 0, state.index)
    last_nl = state.stream.rfind("\n", 0, state.index)
    col = state.index - (last_nl + 1)
    return (line, col)


class ParseError(RuntimeError):
    def __init__(self, expected: FrozenSet[str], state: ParseState):
        self.expected: FrozenSet[str] = expected
        self.state: ParseState = state

    def line_info(self) -> str:
        try:
            return "{}:{}".format(*line_info_at(self.state))
        except (TypeError, AttributeError):  # not a str
            return str(self.state.index)

    def __str__(self) -> str:
        expected_list = sorted(repr(e) for e in self.expected)

        if len(expected_list) == 1:
            return f"expected {expected_list[0]} at {self.line_info()}"
        else:
            return f"expected one of {', '.join(expected_list)} at {self.line_info()}"


@dataclass
class Result(Generic[OUT_co]):
    status: bool
    index: int
    value: OUT_co
    furthest: int
    expected: FrozenSet[str]

    @staticmethod
    def success(index: int, value: OUT) -> Result[OUT]:
        return Result(True, index, value, -1, frozenset())

    # We don't handle types of failures yet, and always
    # either:
    # - don't return these values (e.g. choose another parser)
    # - raise an exception.

    # Therefore, I think it is safe here to use `Any` as type to keep type checker happy
    # The same issue crops up in various branches that return parse failure results
    @staticmethod
    def failure(index: int, expected: str) -> Result[Any]:
        return Result(False, -1, None, index, frozenset([expected]))

    # collect the furthest failure from self and other
    def aggregate(self: Result[OUT], other: Optional[Result[Any]]) -> Result[OUT]:
        if not other:
            return self

        if self.furthest > other.furthest:
            return self
        elif self.furthest == other.furthest:
            # if we both have the same failure state.index, we combine the expected messages.
            return Result(self.status, self.index, self.value, self.furthest, self.expected | other.expected)
        else:
            return Result(self.status, self.index, self.value, other.furthest, other.expected)


class ResultAsException(RuntimeError, Generic[OUT_co]):
    def __init__(self, result: Result[OUT_co]):
        self.result: Result[OUT_co] = result


class Parser(Generic[OUT_co]):
    """
    A Parser is an object that wraps a function whose arguments are
    a string to be parsed and the state.index on which to begin parsing.
    The function should return either Result.success(next_state.index, value),
    where the next state.index is where to continue the parse and the value is
    the yielded value, or Result.failure(state.index, expected), where expected
    is a string indicating what was expected, and the state.index is the state.index
    of the failure.
    """

    def __init__(self, wrapped_fn: Callable[[ParseState], Result[OUT_co]]):
        self.wrapped_fn: Callable[[ParseState], Result[OUT_co]] = wrapped_fn

    def __call__(self, state: ParseState) -> Result[OUT_co]:
        try:
            return self.wrapped_fn(state)
        except ResultAsException as exception:  # type: ignore
            return exception.result  # type: ignore

    def parse(self, stream: str) -> OUT_co:
        """Parse a string and return the result or raise a ParseError."""
        (result, _) = (self << eof).parse_partial(stream)
        return result

    def parse_partial(self, stream: str) -> Tuple[OUT_co, str]:
        """
        Parse the longest possible prefix of a given string.
        Return a tuple of the result and the rest of the string,
        or raise a ParseError.
        """
        result = self(ParseState.start(stream))

        if result.status:
            return (result.value, stream[result.index :])
        else:
            raise ParseError(result.expected, ParseState(stream, result.furthest))

    def parse_state(self, state: ParseState) -> Tuple[OUT_co, ParseState]:
        result = self(state)

        if result.status:
            return (result.value, state.at(result.index))
        else:
            raise ResultAsException(result)

    def bind(self: Parser[OUT1], bind_fn: Callable[[OUT1], Parser[OUT2]]) -> Parser[OUT2]:
        @Parser
        def bound_parser(state: ParseState) -> Result[OUT2]:
            result: Result[OUT1] = self(state)

            if result.status:
                next_parser = bind_fn(result.value)
                return next_parser(state.at(result.index)).aggregate(result)
            else:
                return result  # type: ignore

        return bound_parser

    def map(self: Parser[OUT1], map_fn: Callable[[OUT1], OUT2]) -> Parser[OUT2]:
        return self.bind(lambda res: success(map_fn(res)))

    def concat(self: Parser[List[str]]) -> Parser[str]:
        return self.map("".join)

    def then(self: Parser[Any], other: Parser[OUT2]) -> Parser[OUT2]:
        return (self & other).map(lambda t: t[1])

    def skip(self: Parser[OUT1], other: Parser[Any]) -> Parser[OUT1]:
        return (self & other).map(lambda t: t[0])

    def result(self: Parser[Any], res: OUT2) -> Parser[OUT2]:
        return self >> success(res)

    def times(self: Parser[OUT_co], min: int, max: int | float | None = None) -> Parser[List[OUT_co]]:
        the_max: int | float
        if max is None:
            the_max = min
        else:
            the_max = max

        @Parser
        def times_parser(state: ParseState) -> Result[List[OUT_co]]:
            values: List[OUT_co] = []
            times = 0
            result = None

            while times < the_max:
                result = self(state).aggregate(result)
                if result.status:
                    values.append(result.value)
                    state = state.at(result.index)
                    times += 1
                elif times >= min:
                    break
                else:
                    return result  # type: ignore

            return Result.success(state.index, values).aggregate(result)

        return times_parser

    def many(self: Parser[OUT_co]) -> Parser[List[OUT_co]]:
        return self.times(0, float("inf"))

    def at_most(self: Parser[OUT_co], n: int) -> Parser[List[OUT_co]]:
        return self.times(0, n)

    def at_least(self: Parser[OUT_co], n: int) -> Parser[List[OUT_co]]:
        return self.times(min=n, max=float("inf"))

    @overload
    def optional(self: Parser[OUT1], default: Literal[None] = None) -> Parser[OUT1 | None]:
        ...

    @overload
    def optional(self: Parser[OUT1], default: OUT2) -> Parser[OUT1 | OUT2]:
        ...

    def optional(self: Parser[OUT1], default: Optional[OUT2] = None) -> Parser[OUT1 | Optional[OUT2]]:
        return self.times(0, 1).map(lambda v: v[0] if v else default)

    def until(
        self: Parser[OUT_co],
        other: Parser[Any],
        min: int = 0,
        max: int | float = float("inf"),
    ) -> Parser[List[OUT_co]]:
        @Parser
        def until_parser(state: ParseState) -> Result[List[OUT_co]]:
            values: List[OUT_co] = []
            times = 0
            while True:
                # try parser first
                res = other(state)
                if res.status and times >= min:
                    return Result.success(state.index, values)

                # exceeded max?
                if times >= max:
                    # return failure, it matched parser more than max times
                    return Result.failure(state.index, f"at most {max} items")

                # failed, try parser
                result = self(state)
                if result.status:
                    # consume
                    values.append(result.value)
                    state = state.at(result.index)
                    times += 1
                elif times >= min:
                    # return failure, parser is not followed by other
                    return Result.failure(state.index, "did not find other parser")
                else:
                    # return failure, it did not match parser at least min times
                    return Result.failure(state.index, f"at least {min} items; got {times} item(s)")

        return until_parser

    def sep_by(
        self: Parser[OUT], sep: Parser[Any], *, min: int = 0, max: int | float = float("inf")
    ) -> Parser[List[OUT]]:
        zero_times = success(cast(List[OUT], []))
        if max == 0:
            return zero_times

        res = self.as_list() + (sep >> self).times(min - 1, max - 1)
        if min == 0:
            res = res | zero_times
        return res

    def desc(self, description: str) -> Parser[OUT_co]:
        @Parser
        def desc_parser(state: ParseState) -> Result[OUT_co]:
            result = self(state)
            if result.status:
                return result
            else:
                return Result.failure(state.index, description)

        return desc_parser

    def mark(self: Parser[OUT_co]) -> Parser[Tuple[Tuple[int, int], OUT_co, Tuple[int, int]]]:
        return seq(line_info, self, line_info)

    def tag(self: Parser[OUT], name: str) -> Parser[Tuple[str, OUT]]:
        return self.map(lambda v: (name, v))

    def should_fail(self: Parser[OUT], description: str) -> Parser[Result[OUT]]:
        @Parser
        def fail_parser(state: ParseState) -> Result[Result[OUT]]:
            res = self(state)
            if res.status:
                return Result.failure(state.index, description)
            return Result.success(state.index, res)

        return fail_parser

    # Special cases for adding tuples
    # We have to unroll each number of tuple elements for `other` because PEP-646
    # only allows one "Unpack" in a Tuple (if we could have two, the return
    # type could use two Unpacks
    @overload
    def __add__(self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[Tuple[OUT1]]) -> Parser[Tuple[Unpack[OUT_T], OUT1]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[Tuple[OUT1, OUT2]]
    ) -> Parser[Tuple[Unpack[OUT_T], OUT1, OUT2]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[Tuple[OUT1, OUT2, OUT3]]
    ) -> Parser[Tuple[Unpack[OUT_T], OUT1, OUT2, OUT3]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[Tuple[OUT1, OUT2, OUT3, OUT4]]
    ) -> Parser[Tuple[Unpack[OUT_T], OUT1, OUT2, OUT3, OUT4]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[Tuple[OUT1, OUT2, OUT3, OUT4, OUT5]]
    ) -> Parser[Tuple[Unpack[OUT_T], OUT1, OUT2, OUT3, OUT4, OUT5]]:
        ...

    # This covers tuples where `other` has more elements than the above overloads
    # and the `self` and `other` tuples have the same homogeneous type
    @overload
    def __add__(self: Parser[Tuple[OUT, ...]], other: Parser[Tuple[OUT, ...]]) -> Parser[Tuple[OUT, ...]]:
        ...

    # Cover the rest of cases which can't return a homogeneous tuple
    @overload
    def __add__(self: Parser[Tuple[Any, ...]], other: Parser[Tuple[Any, ...]]) -> Parser[Tuple[Any, ...]]:
        ...

    # Addable parsers which return the same type
    @overload
    def __add__(self: Parser[SupportsAdd[Any, _T_co]], other: Parser[SupportsAdd[Any, _T_co]]) -> Parser[_T_co]:
        ...

    def __add__(self: Parser[Any], other: Parser[Any]) -> Parser[Any]:
        return (self & other).combine(operator.add)

    def __mul__(self: Parser[OUT], other: range | int) -> Parser[List[OUT]]:
        if isinstance(other, range):
            return self.times(other.start, other.stop - 1)
        return self.times(other)

    def __or__(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[Union[OUT1, OUT2]]:
        @Parser
        def alt_parser(state: ParseState) -> Result[Union[OUT1, OUT2]]:
            result0 = None

            result1 = self(state).aggregate(result0)
            if result1.status:
                return result1

            result2 = other(state).aggregate(result1)
            return result2

        return alt_parser

    def __and__(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[tuple[OUT1, OUT2]]:
        @Parser
        def and_parser(state: ParseState) -> Result[tuple[OUT1, OUT2]]:
            self_result = self(state)
            if not self_result.status:
                return self_result  # type: ignore
            other_result = other(ParseState(state.stream, self_result.index)).aggregate(self_result)
            if not other_result.status:
                return other_result  # type: ignore

            return Result.success(other_result.index, (self_result.value, other_result.value)).aggregate(other_result)

        return and_parser

    def pair(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[tuple[OUT1, OUT2]]:
        """TODO alternative name for `&`, decide on naming"""
        return self & other

    def as_tuple(self: Parser[OUT]) -> Parser[Tuple[OUT]]:
        return self.map(lambda value: (value,))

    def as_list(self: Parser[OUT]) -> Parser[List[OUT]]:
        return self.map(lambda value: [value])

    def append(self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[OUT2]) -> Parser[Tuple[Unpack[OUT_T], OUT2]]:
        """
        Take a parser which produces a tuple of values, and add another parser's result
        to the end of that tuples
        """
        return self.bind(lambda self_value: other.bind(lambda other_value: success((*self_value, other_value))))

    def combine(self: Parser[Tuple[Unpack[OUT_T]]], combine_fn: Callable[[Unpack[OUT_T]], OUT2]) -> Parser[OUT2]:
        """
        Apply ``combine_fn`` to the parser result, which must be a tuple. The result
        is passed as `*args` to ``combine_fn``.
        """
        return self.bind(lambda value: success(combine_fn(*value)))

    def zip(self: Parser[OUT], iterable: Sequence[OUT2]) -> Parser[List[Tuple[OUT2, OUT]]]:
        return self.times(len(iterable)).map(lambda values: list(zip(iterable, values)))

    # haskelley operators, for fun #

    # >>

    def __rshift__(self, other: Parser[OUT]) -> Parser[OUT]:
        return self.then(other)

    # <<
    def __lshift__(self, other: Parser[Any]) -> Parser[OUT_co]:
        return self.skip(other)


def forward_parser(fn: Callable[[], Iterator[Parser[T]]]) -> Parser[T]:
    @Parser
    @wraps(fn)
    def generated(state: ParseState) -> Result[T]:
        iterator = fn()
        parser = next(iterator)
        result = parser(state)
        return result

    return generated


# A convenience type for defining forward references to parsers using a generator
ParserReference = Generator[Parser[T], T, T]


index = Parser(lambda state: Result.success(state.index, state.index))
line_info = Parser(lambda state: Result.success(state.index, line_info_at(state)))


def success(val: OUT) -> Parser[OUT]:
    return Parser(lambda state: Result.success(state.index, val))


def fail(expected: str) -> Parser[None]:
    return Parser(lambda state: Result.failure(state.index, expected))


def string(s: str, transform: Callable[[str], str] = noop) -> Parser[str]:
    slen = len(s)
    transformed_s = transform(s)

    @Parser
    def string_parser(state: ParseState) -> Result[str]:
        if transform(state.stream[state.index : state.index + slen]) == transformed_s:
            return Result.success(state.index + slen, s)
        else:
            return Result.failure(state.index, s)

    return string_parser


PatternType = Union[str, Pattern[str]]


@overload
def regex(pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Literal[0] = 0) -> Parser[str]:
    ...


@overload
def regex(pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: str | int) -> Parser[str]:
    ...


@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Tuple[str | int]
) -> Parser[Tuple[str]]:
    ...


@overload
def regex(pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: TUP2[str | int]) -> Parser[TUP2[str]]:
    ...


@overload
def regex(pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: TUP3[str | int]) -> Parser[TUP3[str]]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: TUP4[str | int],
) -> Parser[TUP4[str]]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: TUP5[str | int],
) -> Parser[TUP5[str]]:
    ...


def at_least_len_2(
    value: TUP1[T] | TUP2[T] | TUP3[T] | TUP4[T] | TUP5[T] | Tuple[T, ...]
) -> TypeGuard[TUP2[T] | TUP3[T] | TUP4[T] | TUP5[T] | Tuple[T, ...]]:
    return len(value) >= 2


def has_len_1(value: TUP1[T] | TUP2[T] | TUP3[T] | TUP4[T] | TUP5[T] | Tuple[T, ...]) -> TypeGuard[TUP1[T]]:
    return len(value) == 1


def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: str
    | int
    | TUP1[str | int]
    | TUP2[str | int]
    | TUP3[str | int]
    | TUP4[str | int]
    | TUP5[str | int]
    | Tuple[str | int, ...] = 0,
) -> Parser[str | Tuple[str, ...]]:
    if isinstance(pattern, str):
        exp = re.compile(pattern, flags)
    else:
        exp = pattern

    if isinstance(group, tuple) and at_least_len_2(group):
        first_group, second_group, *groups = group

        @Parser
        def regex_parser_tuple(state: ParseState) -> Result[Tuple[str, ...]]:
            match = exp.match(state.stream, state.index)
            if match:
                return Result.success(match.end(), match.group(first_group, second_group, *groups))
            else:
                return Result.failure(state.index, exp.pattern)

        return regex_parser_tuple

    if isinstance(group, tuple) and has_len_1(group):
        target_group = group[0]
    elif isinstance(group, tuple):
        target_group = 0
    else:
        target_group = group

    @Parser
    def regex_parser(state: ParseState) -> Result[str]:
        match = exp.match(state.stream, state.index)
        if match:
            return Result.success(match.end(), match.group(target_group))
        else:
            return Result.failure(state.index, exp.pattern)

    return regex_parser


# Each number of args needs to be typed separately
@overload
def seq(
    __parser_1: Parser[OUT1],
    __parser_2: Parser[OUT2],
    __parser_3: Parser[OUT3],
    __parser_4: Parser[OUT4],
    __parser_5: Parser[OUT5],
    __parser_6: Parser[OUT6],
) -> Parser[Tuple[OUT1, OUT2, OUT3, OUT4, OUT5, OUT6]]:
    ...


@overload
def seq(
    __parser_1: Parser[OUT1],
    __parser_2: Parser[OUT2],
    __parser_3: Parser[OUT3],
    __parser_4: Parser[OUT4],
    __parser_5: Parser[OUT5],
) -> Parser[Tuple[OUT1, OUT2, OUT3, OUT4, OUT5]]:
    ...


@overload
def seq(
    __parser_1: Parser[OUT1], __parser_2: Parser[OUT2], __parser_3: Parser[OUT3], __parser_4: Parser[OUT4]
) -> Parser[Tuple[OUT1, OUT2, OUT3, OUT4]]:
    ...


@overload
def seq(
    __parser_1: Parser[OUT1], __parser_2: Parser[OUT2], __parser_3: Parser[OUT3]
) -> Parser[Tuple[OUT1, OUT2, OUT3]]:
    ...


@overload
def seq(__parser_1: Parser[OUT1], __parser_2: Parser[OUT2]) -> Parser[Tuple[OUT1, OUT2]]:
    ...


@overload
def seq(__parser_1: Parser[OUT1]) -> Parser[Tuple[OUT1]]:
    ...


@overload
def seq(*parsers: Parser[Any]) -> Parser[Tuple[Any, ...]]:
    ...


def seq(*parsers: Parser[Any]) -> Parser[Tuple[Any, ...]]:
    if not parsers:
        raise ValueError()
    first, *remainder = parsers
    parser = first.as_tuple()
    for p in remainder:
        parser = parser.append(p)  # type: ignore
    return parser


# TODO the rest of the functions here need type annotations.

# One problem is that `test_item` and `match_item` are assumning that the input
# type might not be str, but arbitrary types, including heterogeneous
# lists. We have no generic parameter for the input state.stream type
# yet, for simplicity.


def test_char(func: Callable[[str], bool], description: str) -> Parser[str]:
    @Parser
    def test_char_parser(state: ParseState) -> Result[str]:
        if state.index < len(state.stream):
            if func(state.stream[state.index]):
                return Result.success(state.index + 1, state.stream[state.index])
        return Result.failure(state.index, description)

    return test_char_parser


def match_char(char: str, description: Optional[str] = None) -> Parser[str]:
    if description is None:
        description = char
    return test_char(lambda i: char == i, description)


def string_from(*strings: str, transform: Callable[[str], str] = noop) -> Parser[str]:
    # Sort longest first, so that overlapping options work correctly
    return reduce(operator.or_, [string(s, transform) for s in sorted(strings, key=len, reverse=True)])


def char_from(string: str) -> Parser[str]:
    return test_char(lambda c: c in string, "[" + string + "]")


def peek(parser: Parser[OUT]) -> Parser[OUT]:
    @Parser
    def peek_parser(state: ParseState) -> Result[OUT]:
        result = parser(state)
        if result.status:
            return Result.success(state.index, result.value)
        else:
            return result

    return peek_parser


any_char = test_char(lambda c: True, "any character")

whitespace = regex(r"\s+")

letter = test_char(lambda c: c.isalpha(), "a letter")

digit = test_char(lambda c: c.isdigit(), "a digit")

decimal_digit = char_from("0123456789")


@Parser
def eof(state: ParseState) -> Result[None]:
    if state.index >= len(state.stream):
        return Result.success(state.index, None)
    else:
        return Result.failure(state.index, "EOF")


E = TypeVar("E", bound=enum.Enum)


def from_enum(enum_cls: type[E], transform: Callable[[str], str] = noop) -> Parser[E]:
    items = sorted(
        ((str(enum_item.value), enum_item) for enum_item in enum_cls), key=lambda t: len(t[0]), reverse=True
    )
    return reduce(operator.or_, [string(value, transform=transform).result(enum_item) for value, enum_item in items])


# Dataclass parsers
def take(
    parser: Parser[OUT],
    *,
    init: bool = True,
    repr: bool = True,
    hash: Union[bool, None] = None,
    compare: bool = True,
    metadata: Union[Mapping[Any, Any], None] = None,
) -> OUT:
    if metadata is None:
        metadata = {}
    return field(init=init, repr=repr, hash=hash, compare=compare, metadata={**metadata, "parser": parser})


class DataClassProtocol(Protocol):
    __dataclass_fields__: ClassVar[Dict[str, Field[Any]]]
    __init__: Callable[..., None]


OUT_D = TypeVar("OUT_D", bound=DataClassProtocol)


def gather(datatype: Type[OUT_D]) -> Parser[OUT_D]:
    """Parse all fields of a dataclass parser in order."""

    @Parser
    def parser(state: ParseState) -> Result[OUT_D]:
        parsed_fields: Dict[str, Any] = {}
        for dataclass_field in fields(datatype):
            if "parser" not in dataclass_field.metadata:
                continue
            parser: Parser[Any] = dataclass_field.metadata["parser"]
            result = parser(state)
            if not result.status:
                return result  # type: ignore
            state = state.at(result.index)
            parsed_fields[dataclass_field.name] = result.value

        return Result.success(state.index, datatype(**parsed_fields))

    return parser


def dataclass_permutation_parser(datatype: Type[OUT_D]) -> Parser[OUT_D]:
    """Parse all fields of a dataclass parser in any order."""

    @Parser
    def data_parser(state: ParseState) -> Result[OUT_D]:
        parsed_fields: Dict[str, Any] = {}
        parsers: Dict[str, Parser[Any]] = {
            field.name: field.metadata["parser"] for field in fields(datatype) if "parser" in field.metadata
        }
        failures: List[str] = []
        while parsers:
            failures = []
            for field_name, parser in tuple(parsers.items()):
                result = parser(state)
                if not result.status:
                    failures.append(f"'{field_name}': {', '.join(result.expected)}")
                    continue

                state = state.at(result.index)
                parsed_fields[field_name] = result.value
                parsers.pop(field_name)
                break
            else:
                # No parsers matched
                return Result.failure(state.index, f"Any of: {', '.join(failures)}")

        return Result.success(state.index, datatype(**parsed_fields))

    return data_parser
