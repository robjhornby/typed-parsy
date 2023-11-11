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
    LiteralString,
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

from typing_extensions import (
    Literal,
    Protocol,
    TypeGuard,
    TypeVarTuple,
    Unpack,
)

_T = TypeVar("_T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_T6 = TypeVar("_T6")

_Ts = TypeVarTuple("_Ts")

_OUT_co = TypeVar("_OUT_co", covariant=True)

_TLiteral = TypeVar("_TLiteral", bound=LiteralString)

_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)


class SupportsAdd(Protocol[_T_contra, _T_co]):
    def __add__(self, other: _T_contra, /) -> _T_co:
        ...


class SupportsRAdd(Protocol[_T_contra, _T_co]):
    def __radd__(self, other: _T_contra, /) -> _T_co:
        ...


@dataclass(frozen=True)
class ParseState:
    stream: str
    index: int

    @staticmethod
    def start(stream: str) -> ParseState:
        return ParseState(stream, 0)

    def at(self: ParseState, index: int) -> ParseState:
        return ParseState(self.stream, index)

    def apply(self, parser: Parser[_T]) -> Tuple[_T, ParseState]:
        return parser.parse_state(self)

    def success(self, value: _T) -> Result[_T]:
        return Result.success(self.index, value)


@dataclass
class State:
    state: ParseState

    def apply(self, parser: Parser[_T]) -> _T:
        result, self.state = parser.parse_state(self.state)
        return result

    def success(self, value: _T) -> Result[_T]:
        return Result.success(self.state.index, value)

    @property
    def remaining(self) -> str:
        return self.state.stream[self.state.index :]


def stateful_parser(fn: Callable[[State], Result[_T]]) -> Parser[_T]:
    @Parser
    def the_parser(parse_state: ParseState) -> Result[_T]:
        state = State(parse_state)
        return fn(state)

    return the_parser


def line_info_at(state: ParseState) -> Tuple[int, int]:
    if state.index > len(state.stream):
        raise ValueError("invalid state.index")
    line = state.stream.count("\n", 0, state.index)
    last_nl = state.stream.rfind("\n", 0, state.index)
    col = state.index - (last_nl + 1)
    return (line, col)


class ParseError(RuntimeError):
    def __init__(self, expected: FrozenSet[str], state: ParseState) -> None:
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
class Result(Generic[_OUT_co]):
    status: bool
    index: int
    value: _OUT_co
    furthest: int
    expected: FrozenSet[str]

    @staticmethod
    def success(index: int, value: _T) -> Result[_T]:
        return Result(True, index, value, -1, frozenset())

    @staticmethod
    def failure(index: int, expected: str) -> Result[Any]:
        return Result(False, -1, None, index, frozenset([expected]))

    # collect the furthest failure from self and other
    def aggregate(self: Result[_T], other: Optional[Result[Any]]) -> Result[_T]:
        if not other:
            return self

        if self.furthest > other.furthest:
            return self
        elif self.furthest == other.furthest:
            # if we both have the same failure state.index, we combine the expected messages.
            return Result(
                self.status,
                self.index,
                self.value,
                self.furthest,
                self.expected | other.expected,
            )
        else:
            return Result(
                self.status, self.index, self.value, other.furthest, other.expected
            )


class ResultAsException(RuntimeError, Generic[_OUT_co]):
    def __init__(self, result: Result[_OUT_co]) -> None:
        self.result: Result[_OUT_co] = result


class Parser(Generic[_OUT_co]):
    """
    A Parser is an object that wraps a function whose arguments are
    a string to be parsed and the state.index on which to begin parsing.
    The function should return either Result.success(next_state.index, value),
    where the next state.index is where to continue the parse and the value is
    the yielded value, or Result.failure(state.index, expected), where expected
    is a string indicating what was expected, and the state.index is the state.index
    of the failure.
    """

    def __init__(self, wrapped_fn: Callable[[ParseState], Result[_OUT_co]]) -> None:
        self.wrapped_fn: Callable[[ParseState], Result[_OUT_co]] = wrapped_fn

    def __call__(self, state: ParseState) -> Result[_OUT_co]:
        try:
            return self.wrapped_fn(state)
        except ResultAsException as exception:  # type: ignore[unused-ignore]
            return exception.result  #  type: ignore

    def parse(self, stream: str) -> _OUT_co:
        """Parse a string and return the result or raise a ParseError."""
        (result, _) = (self << eof).parse_partial(stream)
        return result

    def parse_partial(self, stream: str) -> Tuple[_OUT_co, str]:
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

    def parse_state(self, state: ParseState) -> Tuple[_OUT_co, ParseState]:
        result = self(state)

        if result.status:
            return (result.value, state.at(result.index))
        else:
            raise ResultAsException(result)

    def bind(self: Parser[_T1], bind_fn: Callable[[_T1], Parser[_T2]]) -> Parser[_T2]:
        @Parser
        def bound_parser(state: ParseState) -> Result[_T2]:
            result: Result[_T1] = self(state)

            if result.status:
                next_parser = bind_fn(result.value)
                return next_parser(state.at(result.index)).aggregate(result)
            else:
                return result  # type: ignore

        return bound_parser

    def map(self: Parser[_T1], map_fn: Callable[[_T1], _T2]) -> Parser[_T2]:
        return self.bind(lambda res: success(map_fn(res)))

    def concat(self: Parser[List[str]]) -> Parser[str]:
        return self.map("".join)

    def then(self: Parser[Any], other: Parser[_T2]) -> Parser[_T2]:
        return (self & other).map(lambda t: t[1])

    def skip(self: Parser[_T1], other: Parser[Any]) -> Parser[_T1]:
        return (self & other).map(lambda t: t[0])

    def result(self: Parser[Any], res: _T) -> Parser[_T]:
        return self >> success(res)

    def times(
        self: Parser[_OUT_co], min: int, max: int | float | None = None
    ) -> Parser[List[_OUT_co]]:
        the_max: int | float
        if max is None:
            the_max = min
        else:
            the_max = max

        @Parser
        def times_parser(state: ParseState) -> Result[List[_OUT_co]]:
            values: List[_OUT_co] = []
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

    def many(self: Parser[_OUT_co]) -> Parser[List[_OUT_co]]:
        return self.times(0, float("inf"))

    def at_most(self: Parser[_OUT_co], n: int) -> Parser[List[_OUT_co]]:
        return self.times(0, n)

    def at_least(self: Parser[_OUT_co], n: int) -> Parser[List[_OUT_co]]:
        return self.times(min=n, max=float("inf"))

    @overload
    def optional(
        self: Parser[_T1], default: Literal[None] = None
    ) -> Parser[_T1 | None]:
        ...

    @overload
    def optional(self: Parser[_T1], default: _T2) -> Parser[_T1 | _T2]:
        ...

    def optional(
        self: Parser[_T1], default: Optional[_T2] = None
    ) -> Parser[_T1 | Optional[_T2]]:
        return self.times(0, 1).map(lambda v: v[0] if v else default)

    def until(
        self: Parser[_OUT_co],
        other: Parser[Any],
        min: int = 0,
        max: int | float = float("inf"),
    ) -> Parser[List[_OUT_co]]:
        @Parser
        def until_parser(state: ParseState) -> Result[List[_OUT_co]]:
            values: List[_OUT_co] = []
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
                    return Result.failure(
                        state.index, f"at least {min} items; got {times} item(s)"
                    )

        return until_parser

    def sep_by(
        self: Parser[_T],
        sep: Parser[Any],
        *,
        min: int = 0,
        max: int | float = float("inf"),
    ) -> Parser[List[_T]]:
        zero_times = success(cast(List[_T], []))
        if max == 0:
            return zero_times

        res = self.list() + (sep >> self).times(min - 1, max - 1)
        if min == 0:
            res = res | zero_times
        return res

    def desc(self, description: str) -> Parser[_OUT_co]:
        @Parser
        def desc_parser(state: ParseState) -> Result[_OUT_co]:
            result = self(state)
            if result.status:
                return result
            else:
                return Result.failure(state.index, description)

        return desc_parser

    def should_fail(self: Parser[_T], description: str) -> Parser[Result[_T]]:
        @Parser
        def fail_parser(state: ParseState) -> Result[Result[_T]]:
            res = self(state)
            if res.status:
                return Result.failure(state.index, description)
            return Result.success(state.index, res)

        return fail_parser

    # Special cases for adding tuples
    # We have to unroll each number of tuple elements for `other` because PEP-646
    # only allows one "Unpack" in a Tuple (if we could have two, the return
    # type could use two Unpacks to cover most of these cases)
    @overload
    def __add__(
        self: Parser[Tuple[_T, Unpack[_Ts]]], other: Parser[Tuple[_T1]]
    ) -> Parser[Tuple[_T, Unpack[_Ts], _T1]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[_T]], other: Parser[Tuple[_T1, Unpack[_Ts]]]
    ) -> Parser[Tuple[_T, _T1, Unpack[_Ts]]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[_T, Unpack[_Ts]]], other: Parser[Tuple[_T1, _T2]]
    ) -> Parser[Tuple[_T, Unpack[_Ts], _T1, _T2]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[_T, Unpack[_Ts]]], other: Parser[Tuple[_T1, _T2, _T3]]
    ) -> Parser[Tuple[_T, Unpack[_Ts], _T1, _T2, _T3]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[_T, Unpack[_Ts]]],
        other: Parser[Tuple[_T1, _T2, _T3, _T4]],
    ) -> Parser[Tuple[_T, Unpack[_Ts], _T1, _T2, _T3, _T4]]:
        ...

    @overload
    def __add__(
        self: Parser[Tuple[_T, Unpack[_Ts]]],
        other: Parser[Tuple[_T1, _T2, _T3, _T4, _T5]],
    ) -> Parser[Tuple[_T, Unpack[_Ts], _T1, _T2, _T3, _T4, _T5]]:
        ...

    # This covers tuples where `other` has more elements than the above overloads
    # and the `self` and `other` tuples have the same homogeneous type
    @overload
    def __add__(
        self: Parser[Tuple[_T, ...]], other: Parser[Tuple[_T, ...]]
    ) -> Parser[Tuple[_T, ...]]:
        ...

    # Cover the rest of cases which can't return a homogeneous tuple
    @overload
    def __add__(
        self: Parser[Tuple[Any, ...]], other: Parser[Tuple[Any, ...]]
    ) -> Parser[Tuple[Any, ...]]:
        ...

    # Addable parsers which return the same type
    @overload
    def __add__(
        self: Parser[SupportsAdd[_T_contra, _T_co]], other: Parser[_T_contra]
    ) -> Parser[_T_co]:
        ...

    @overload
    def __add__(
        self: Parser[_T_contra], other: Parser[SupportsRAdd[_T_contra, _T_co]]
    ) -> Parser[_T_co]:
        ...

    def __add__(self: Parser[Any], other: Parser[Any]) -> Parser[Any]:
        return (self & other).combine(operator.add)

    def __mul__(self: Parser[_T], other: range | int) -> Parser[List[_T]]:
        if isinstance(other, range):
            return self.times(other.start, other.stop - 1)
        return self.times(other)

    def __or__(self: Parser[_T1], other: Parser[_T2]) -> Parser[Union[_T1, _T2]]:
        @Parser
        def alt_parser(state: ParseState) -> Result[Union[_T1, _T2]]:
            result0 = None

            result1 = self(state).aggregate(result0)
            if result1.status:
                return result1

            result2 = other(state).aggregate(result1)
            return result2

        return alt_parser

    def __and__(self: Parser[_T1], other: Parser[_T2]) -> Parser[tuple[_T1, _T2]]:
        @Parser
        def and_parser(state: ParseState) -> Result[tuple[_T1, _T2]]:
            self_result = self(state)
            if not self_result.status:
                return self_result  # type: ignore
            other_result = other(ParseState(state.stream, self_result.index)).aggregate(
                self_result
            )
            if not other_result.status:
                return other_result  # type: ignore

            return Result.success(
                other_result.index, (self_result.value, other_result.value)
            ).aggregate(other_result)

        return and_parser

    def pair(self: Parser[_T1], other: Parser[_T2]) -> Parser[tuple[_T1, _T2]]:
        """TODO alternative name for `&`, decide on naming"""
        return self & other

    def tuple(self: Parser[_T]) -> Parser[Tuple[_T]]:
        """Wrap the result in a tuple."""
        return self.map(lambda value: (value,))

    def list(self: Parser[_T]) -> Parser[List[_T]]:
        """Wrap the result in a list."""
        return self.map(lambda value: [value])

    def append(
        self: Parser[Tuple[Unpack[_Ts]]], other: Parser[_T2]
    ) -> Parser[Tuple[Unpack[_Ts], _T2]]:
        """
        Take a parser which produces a tuple of values, and add another parser's result
        to the end of that tuples
        """
        return self.bind(
            lambda self_value: other.bind(
                lambda other_value: success((*self_value, other_value))
            )
        )

    def combine(
        self: Parser[Tuple[Unpack[_Ts]]], combine_fn: Callable[[Unpack[_Ts]], _T2]
    ) -> Parser[_T2]:
        """
        Apply ``combine_fn`` to the parser result, which must be a tuple. The result
        is passed as `*args` to ``combine_fn``.
        """
        return self.bind(lambda value: success(combine_fn(*value)))

    def zip(self: Parser[_T], iterable: Sequence[_T2]) -> Parser[List[Tuple[_T2, _T]]]:
        return self.times(len(iterable)).map(lambda values: list(zip(iterable, values)))

    # haskelley operators, for fun #

    # >>

    def __rshift__(self, other: Parser[_T]) -> Parser[_T]:
        return self.then(other)

    # <<
    def __lshift__(self, other: Parser[Any]) -> Parser[_OUT_co]:
        return self.skip(other)


def forward_parser(fn: Callable[[], Iterator[Parser[_T]]]) -> Parser[_T]:
    @Parser
    @wraps(fn)
    def generated(state: ParseState) -> Result[_T]:
        iterator = fn()
        parser = next(iterator)
        result = parser(state)
        return result

    return generated


# A convenience type for defining forward references to parsers using a generator
ParserReference = Generator[Parser[_T], _T, _T]


index = Parser(lambda state: Result.success(state.index, state.index))
line_info = Parser(lambda state: Result.success(state.index, line_info_at(state)))


def success(val: _T) -> Parser[_T]:
    return Parser(lambda state: Result.success(state.index, val))


def fail(expected: str) -> Parser[None]:
    return Parser(lambda state: Result.failure(state.index, expected))


def string(s: str) -> Parser[str]:
    slen = len(s)

    @Parser
    def string_parser(state: ParseState) -> Result[str]:
        if state.stream[state.index : state.index + slen] == s:
            return Result.success(state.index + slen, s)
        else:
            return Result.failure(state.index, s)

    return string_parser


def has_multiple_elements(
    value: Tuple[_T]
    | Tuple[_T, _T]
    | Tuple[_T, _T, _T]
    | Tuple[_T, _T, _T, _T]
    | Tuple[_T, _T, _T, _T, _T]
    | Tuple[_T, ...],
) -> TypeGuard[
    Tuple[_T, _T]
    | Tuple[_T, _T, _T]
    | Tuple[_T, _T, _T, _T]
    | Tuple[_T, _T, _T, _T, _T]
    | Tuple[_T, ...]
]:
    return len(value) >= 2


def has_single_element(
    value: Tuple[_T]
    | Tuple[_T, _T]
    | Tuple[_T, _T, _T]
    | Tuple[_T, _T, _T, _T]
    | Tuple[_T, _T, _T, _T, _T]
    | Tuple[_T, ...],
) -> TypeGuard[Tuple[_T]]:
    return len(value) == 1


PatternType = Union[str, Pattern[str]]


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Literal[0] = 0,
) -> Parser[str]:
    ...


@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: str | int
) -> Parser[str]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int],
) -> Parser[str]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int],
) -> Parser[Tuple[str, str]]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int, str | int],
) -> Parser[Tuple[str, str, str]]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int, str | int, str | int],
) -> Parser[Tuple[str, str, str, str]]:
    ...


@overload
def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: Tuple[str | int, str | int, str | int, str | int, str | int],
) -> Parser[Tuple[str, str, str, str, str]]:
    ...


def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: str
    | int
    | Tuple[str | int]
    | Tuple[str | int, str | int]
    | Tuple[str | int, str | int, str | int]
    | Tuple[str | int, str | int, str | int, str | int]
    | Tuple[str | int, str | int, str | int, str | int, str | int]
    | Tuple[str | int, ...] = 0,
) -> Parser[str | Tuple[str, ...]]:
    if isinstance(pattern, str):
        exp = re.compile(pattern, flags)
    else:
        exp = pattern

    if isinstance(group, tuple) and has_multiple_elements(group):
        first_group, second_group, *groups = group

        @Parser
        def regex_parser_tuple(state: ParseState) -> Result[Tuple[str, ...]]:
            match = exp.match(state.stream, state.index)
            if match:
                return Result.success(
                    match.end(), match.group(first_group, second_group, *groups)
                )
            else:
                return Result.failure(state.index, exp.pattern)

        return regex_parser_tuple

    if isinstance(group, tuple) and has_single_element(group):
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


# fmt: off
# Each number of args needs to be typed separately
@overload
def seq(
    p1: Parser[_T1], p2: Parser[_T2], p3: Parser[_T3], p4: Parser[_T4], p5: Parser[_T5], p6: Parser[_T6], /,
) -> Parser[Tuple[_T1, _T2, _T3, _T4, _T5, _T6]]: ...

@overload
def seq(
    p1: Parser[_T1], p2: Parser[_T2], p3: Parser[_T3], p4: Parser[_T4], p5: Parser[_T5], /
) -> Parser[Tuple[_T1, _T2, _T3, _T4, _T5]]: ...

@overload
def seq(
    p1: Parser[_T1], p2: Parser[_T2], p3: Parser[_T3], p4: Parser[_T4], /
) -> Parser[Tuple[_T1, _T2, _T3, _T4]]: ...

@overload
def seq(
    p1: Parser[_T1], p2: Parser[_T2], p3: Parser[_T3], /
) -> Parser[Tuple[_T1, _T2, _T3]]: ...

@overload
def seq(p1: Parser[_T1], p2: Parser[_T2], /) -> Parser[Tuple[_T1, _T2]]: ...

@overload
def seq(p1: Parser[_T1], /) -> Parser[Tuple[_T1]]: ...

@overload
def seq(*parsers: Parser[Any]) -> Parser[Tuple[Any, ...]]: ...
# fmt: on


def seq(*parsers: Parser[Any]) -> Parser[Tuple[Any, ...]]:
    if not parsers:
        raise ValueError("The seq parser requires at least one argument")
    first, *remainder = parsers
    parser = first.tuple()
    for p in remainder:
        parser = parser.append(p)  # type: ignore
    return parser


def gate_char(func: Callable[[str], bool]) -> Parser[str]:
    @Parser
    def parser(state: ParseState) -> Result[str]:
        if state.index < len(state.stream):
            if func(state.stream[state.index]):
                return Result.success(state.index + 1, state.stream[state.index])
        return Result.failure(state.index, "Character gate")

    return parser


def string_from(*strings: str) -> Parser[str]:
    return reduce(
        operator.or_,
        # Sort longest first, so that overlapping options work correctly
        (string(s) for s in sorted(strings, key=len, reverse=True)),
    )


def char_from(string: str) -> Parser[str]:
    return gate_char(lambda c: c in string).desc(f"[{string}]")


def peek(parser: Parser[_T]) -> Parser[_T]:
    @Parser
    def peek_parser(state: ParseState) -> Result[_T]:
        result = parser(state)
        if result.status:
            return Result.success(state.index, result.value)
        else:
            return result

    return peek_parser


any_char = gate_char(lambda c: True).desc("any character")

whitespace = regex(r"\s+")

padding = regex(r"\s*")

letter = gate_char(lambda c: c.isalpha()).desc("a letter")

digit = gate_char(lambda c: c.isdigit()).desc("a digit")

decimal_digit = char_from("0123456789")


@Parser
def eof(state: ParseState) -> Result[None]:
    if state.index >= len(state.stream):
        return Result.success(state.index, None)
    else:
        return Result.failure(state.index, "EOF")


E = TypeVar("E", bound=enum.Enum)


def from_enum(enum_cls: type[E]) -> Parser[E]:
    items = sorted(
        (enum_item for enum_item in enum_cls),
        key=lambda e: len(str(e.value)),
        reverse=True,
    )
    return reduce(
        operator.or_,
        [string(str(item.value)).result(item) for item in items],
    )


# Dataclass parsers
def take(
    parser: Parser[_T],
    *,
    init: bool = True,
    repr: bool = True,
    hash: Union[bool, None] = None,
    compare: bool = True,
    metadata: Union[Mapping[Any, Any], None] = None,
) -> _T:
    """
    A dataclass field descriptor used to associate a parser with a dataclass field.

    Use this in a dataclass in conjunction with `gather` to concisely define parsers
    which return dataclass instances.
    """
    if metadata is None:
        metadata = {}
    return cast(
        _T,
        field(
            init=init,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata={**metadata, "parser": parser},
        ),
    )


class DataClassProtocol(Protocol):
    __dataclass_fields__: ClassVar[Dict[str, Field[Any]]]
    __init__: Callable[..., None]


T_D = TypeVar("T_D", bound=DataClassProtocol)


def gather(datatype: Type[T_D]) -> Parser[T_D]:
    """Parse all fields of a dataclass parser in order."""

    @Parser
    def parser(state: ParseState) -> Result[T_D]:
        parsed_fields: Dict[str, Any] = {}
        for dataclass_field in fields(datatype):
            if "parser" not in dataclass_field.metadata:
                continue
            parser: Parser[Any] = dataclass_field.metadata["parser"]
            result = parser(state)
            if not result.status:
                return result
            state = state.at(result.index)
            parsed_fields[dataclass_field.name] = result.value

        return Result.success(state.index, datatype(**parsed_fields))

    return parser


def gather_perm(datatype: Type[T_D]) -> Parser[T_D]:
    """Parse all fields of a dataclass parser in any order."""

    @Parser
    def parser(state: ParseState) -> Result[T_D]:
        parsed_fields: Dict[str, Any] = {}
        parsers: Dict[str, Parser[Any]] = {
            field.name: field.metadata["parser"]
            for field in fields(datatype)
            if "parser" in field.metadata
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

    return parser
