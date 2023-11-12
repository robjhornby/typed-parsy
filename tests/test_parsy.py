# -*- code: utf8 -*-
import enum
import re
from typing import Iterator, List, Union

import pytest

# to stop pytest thinking this function is a test
from parsy import (
    ParseError,
    Parser,
    ParseState,
    Result,
    any_char,
    char_from,
    decimal_digit,
    digit,
    forward_parser,
    from_enum,
    gate_char,
    letter,
    line_info_at,
    peek,
    regex,
    seq,
    string,
    string_from,
    whitespace,
)


class TestParser:
    def test_string(self) -> None:
        parser = string("x")
        assert parser.parse("x") == "x"
        with pytest.raises(ParseError):
            parser.parse("y")
        with pytest.raises(ParseError):
            parser.parse("y")
        with pytest.raises(ParseError):
            parser.parse("dog")

    def test_regex_str(self) -> None:
        parser = regex(r"[0-9]")

        assert parser.parse("1") == "1"
        assert parser.parse("4") == "4"
        with pytest.raises(ParseError):
            parser.parse("x")

    def test_regex_compiled(self) -> None:
        parser = regex(re.compile(r"[0-9]"))
        assert parser.parse("1") == "1"
        with pytest.raises(ParseError):
            parser.parse("x")

    def test_regex_group_number(self) -> None:
        parser = regex(re.compile(r"a([0-9])b"), group=1)
        assert parser.parse("a1b") == "1"
        with pytest.raises(ParseError):
            parser.parse("x")

    def test_regex_group_name(self) -> None:
        parser = regex(re.compile(r"a(?P<name>[0-9])b"), group="name")
        assert parser.parse("a1b") == "1"
        with pytest.raises(ParseError):
            parser.parse("x")

    def test_regex_group_tuple(self) -> None:
        parser = regex(re.compile(r"a([0-9])b([0-9])c"), group=(1, 2))
        assert parser.parse("a1b2c") == ("1", "2")
        with pytest.raises(ParseError):
            parser.parse("x")

    def test_then(self) -> None:
        xy_parser = string("x") >> string("y")
        assert xy_parser.parse("xy") == "y"

        with pytest.raises(ParseError):
            xy_parser.parse("y")
        with pytest.raises(ParseError):
            xy_parser.parse("z")

    def test_bind(self) -> None:
        piped = None

        def binder(x: str) -> Parser[str]:
            nonlocal piped
            piped = x
            return string("y")

        parser = string("x").bind(binder)

        assert parser.parse("xy") == "y"
        assert piped == "x"

        with pytest.raises(ParseError):
            parser.parse("x")

    def test_map(self) -> None:
        parser = digit.map(int)
        assert parser.parse("7") == 7

    def test_and(self) -> None:
        parser = digit & letter
        assert parser.parse("1A") == ("1", "A")

    def test_append(self) -> None:
        parser = digit.pair(letter).append(letter)
        assert parser.parse("1AB") == ("1", "A", "B")

    def test_combine(self) -> None:
        parser = digit.pair(letter).append(letter).combine(lambda a, b, c: (c + b + a))
        assert parser.parse("1AB") == "BA1"

    # def test_combine_mixed_types(self) -> None:
    #     def demo(a: int, b: str, c: bool) -> Tuple[int, str, bool]:
    #         return (a, b, c)

    #     parser = digit.map(int).join(letter).append(digit.map(bool)).combine(demo)
    #     assert parser.parse("1A1") ==  (1, "A", True)

    def test_concat(self) -> None:
        parser = letter.many().concat()
        assert parser.parse("") == ""
        assert parser.parse("abc") == "abc"

    def test_state_parser(self) -> None:
        x = y = None

        @Parser
        def xy(s: ParseState) -> Result[int]:
            nonlocal x
            nonlocal y
            x, s = s.apply(string("x"))
            y, s = s.apply(string("y"))
            return s.success(3)

        assert xy.parse("xy") == 3
        assert x == "x"
        assert y == "y"

    def test_multiple_failures(self) -> None:
        abc = string("a") | string("b") | string("c")

        with pytest.raises(
            ParseError, match="expected one of 'a', 'b', 'c' at 0:0"
        ) as err:
            abc.parse("d")

        assert err.value.expected == frozenset(["a", "b", "c"])

    def test_state_parser_backtracking(self) -> None:
        @Parser
        def xy(s: ParseState) -> Result[None]:
            _, s = s.apply(string("x"))
            _, s = s.apply(string("y"))
            assert False
            return s.success(None)

        parser = xy | string("z")
        # should not finish executing xy()
        assert parser.parse("z") == "z"

    def test_or(self) -> None:
        x_or_y = string("x") | string("y")

        assert x_or_y.parse("x") == "x"
        assert x_or_y.parse("y") == "y"

    def test_or_with_then(self) -> None:
        parser = (string("\\") >> string("y")) | string("z")
        assert parser.parse("\\y") == "y"
        assert parser.parse("z") == "z"

        with pytest.raises(ParseError):
            parser.parse("\\z")

    def test_many(self) -> None:
        letters = letter.many()
        assert letters.parse("x") == ["x"]
        assert letters.parse("xyz") == ["x", "y", "z"]
        assert letters.parse("") == []

        with pytest.raises(ParseError):
            letters.parse("1")

    def test_many_with_then(self) -> None:
        parser = string("x").many() >> string("y")
        assert parser.parse("y") == "y"
        assert parser.parse("xy") == "y"
        assert parser.parse("xxxxxy") == "y"

    def test_times_zero(self) -> None:
        zero_letters = letter.times(0)
        assert zero_letters.parse("") == []

        with pytest.raises(ParseError):
            zero_letters.parse("x")

    def test_times(self) -> None:
        three_letters = letter.times(3)
        assert three_letters.parse("xyz") == ["x", "y", "z"]

        with pytest.raises(ParseError):
            three_letters.parse("xy")
        with pytest.raises(ParseError):
            three_letters.parse("xyzw")

    def test_times_with_then(self) -> None:
        then_digit = letter.times(3) >> digit
        assert then_digit.parse("xyz1") == "1"

        with pytest.raises(ParseError):
            then_digit.parse("xy1")
        with pytest.raises(ParseError):
            then_digit.parse("xyz")
        with pytest.raises(ParseError):
            then_digit.parse("xyzw")

    def test_times_with_min_and_max(self) -> None:
        some_letters = letter.times(2, 4)

        assert some_letters.parse("xy") == ["x", "y"]
        assert some_letters.parse("xyz") == ["x", "y", "z"]
        assert some_letters.parse("xyzw") == ["x", "y", "z", "w"]

        with pytest.raises(ParseError):
            some_letters.parse("x")
        with pytest.raises(ParseError):
            some_letters.parse("xyzwv")

    def test_times_with_min_and_max_and_then(self) -> None:
        then_digit = letter.times(2, 4) >> digit

        assert then_digit.parse("xy1") == "1"
        assert then_digit.parse("xyz1") == "1"
        assert then_digit.parse("xyzw1") == "1"

        with pytest.raises(ParseError):
            then_digit.parse("xy")
        with pytest.raises(ParseError):
            then_digit.parse("xyzw")
        with pytest.raises(ParseError):
            then_digit.parse("xyzwv1")
        with pytest.raises(ParseError):
            then_digit.parse("x1")

    def test_at_most(self) -> None:
        ab = string("ab")
        assert ab.at_most(2).parse("") == []
        assert ab.at_most(2).parse("ab") == ["ab"]
        assert ab.at_most(2).parse("abab") == ["ab", "ab"]
        with pytest.raises(ParseError):
            ab.at_most(2).parse("ababab")

    def test_at_least(self) -> None:
        ab = string("ab")
        assert ab.at_least(2).parse("abab") == ["ab", "ab"]
        assert ab.at_least(2).parse("ababab") == ["ab", "ab", "ab"]
        with pytest.raises(ParseError):
            ab.at_least(2).parse("ab")

        assert ab.at_least(2).parse_partial("abababc") == (["ab", "ab", "ab"], "c")

    def test_until(self) -> None:
        until = string("s").until(string("x"))

        s = "ssssx"
        assert until.parse_partial(s) == (4 * ["s"], "x")
        assert until.then(string("x")).parse(s) == "x"

        s = "ssssxy"
        assert until.parse_partial(s) == (4 * ["s"], "xy")
        assert until.then(string("x")).parse_partial(s) == ("x", "y")

        with pytest.raises(ParseError):
            until.parse("ssssy")
        with pytest.raises(ParseError):
            until.parse("xssssxy")

        assert until.parse_partial("xxx") == ([], "xxx")

        until = regex(".").until(string("x"))
        assert until.parse_partial("xxxx") == ([], "xxxx")

    def test_until_with_min(self) -> None:
        until = string("s").until(string("x"), min=3)

        assert until.parse_partial("sssx") == (3 * ["s"], "x")
        assert until.parse_partial("sssssx") == (5 * ["s"], "x")

        with pytest.raises(ParseError):
            until.parse_partial("ssx")

    def test_until_with_max(self) -> None:
        # until with max
        until = string("s").until(string("x"), max=3)

        assert until.parse_partial("ssx") == (2 * ["s"], "x")
        assert until.parse_partial("sssx") == (3 * ["s"], "x")

        with pytest.raises(ParseError):
            until.parse_partial("ssssx")

    def test_until_with_min_max(self) -> None:
        until = string("s").until(string("x"), min=3, max=5)

        assert until.parse_partial("sssx") == (3 * ["s"], "x")
        assert until.parse_partial("ssssx") == (4 * ["s"], "x")
        assert until.parse_partial("sssssx") == (5 * ["s"], "x")

        with pytest.raises(ParseError) as err:
            until.parse_partial("ssx")
        assert err.value.expected == frozenset({"at least 3 items; got 2 item(s)"})

        with pytest.raises(ParseError) as err:
            until.parse_partial("ssssssx")
        assert err.value.expected == frozenset({"at most 5 items"})

    def test_optional(self) -> None:
        p = string("a").optional()
        assert p.parse("a") == "a"
        assert p.parse("") is None
        p = string("a").optional("b")
        assert p.parse("a") == "a"
        assert p.parse("") == "b"

    def test_sep_by(self) -> None:
        digit_list = digit.map(int).sep_by(string(","))

        assert digit_list.parse("1,2,3,4") == [1, 2, 3, 4]
        assert digit_list.parse("9,0,4,7") == [9, 0, 4, 7]
        assert digit_list.parse("3,7") == [3, 7]
        assert digit_list.parse("8") == [8]
        assert digit_list.parse("") == []

        with pytest.raises(ParseError):
            digit_list.parse("8,")
        with pytest.raises(ParseError):
            digit_list.parse(",9")
        with pytest.raises(ParseError):
            digit_list.parse("82")
        with pytest.raises(ParseError):
            digit_list.parse("7.6")

    def test_sep_by_with_min_and_max(self) -> None:
        digit_list = digit.map(int).sep_by(string(","), min=2, max=4)

        assert digit_list.parse("1,2,3,4") == [1, 2, 3, 4]
        assert digit_list.parse("9,0,4,7") == [9, 0, 4, 7]
        assert digit_list.parse("3,7") == [3, 7]

        with pytest.raises(ParseError):
            digit_list.parse("8")
        with pytest.raises(ParseError):
            digit_list.parse("")
        with pytest.raises(ParseError):
            digit_list.parse("8,")
        with pytest.raises(ParseError):
            digit_list.parse(",9")
        with pytest.raises(ParseError):
            digit_list.parse("82")
        with pytest.raises(ParseError):
            digit_list.parse("7.6")
        assert digit.sep_by(string(" == "), max=0).parse("") == []

    def test_add_tuple(self) -> None:
        """This test code is for checking that pylance gives no type errors"""
        letter_tuple = letter.tuple()
        int_parser = regex(r"\d").map(int)
        two_int_parser = int_parser & int_parser
        barcode = letter_tuple + two_int_parser

        def my_foo(first: str, second: int, third: int) -> str:
            return first + str(third + second)

        foo_parser = barcode.combine(my_foo)

        assert foo_parser.parse("a13") == "a4"

    def test_add_too_long_tuple_uniform_types(self) -> None:
        """This test code is for checking that pylance gives no type errors"""
        letter_tuple = letter.tuple()
        int_parser = regex(r"\d")
        six_int_parser = (
            (int_parser & int_parser)
            .append(int_parser)
            .append(int_parser)
            .append(int_parser)
            .append(int_parser)
        )
        barcode = letter_tuple + six_int_parser

        def my_bar(first: str, *second: str) -> str:
            return first + "-".join(second)

        foo_parser = barcode.combine(my_bar)

        assert foo_parser.parse("a123456") == "a1-2-3-4-5-6"

    def test_add_too_long_tuple_different_types(self) -> None:
        """This test code is for checking that pylance gives no type errors"""
        letter_tuple = letter.tuple()
        int_parser = regex(r"\d").map(int)
        six_int_parser = (
            (int_parser & int_parser)
            .append(int_parser)
            .append(int_parser)
            .append(int_parser)
            .append(int_parser)
        )
        barcode = letter_tuple + six_int_parser

        def my_bar(first: str, *second: int) -> str:
            return first + str(sum(second))

        foo_parser = barcode.combine(my_bar)

        assert foo_parser.parse("a111111") == "a6"

    def test_add_list(self) -> None:
        """This test code is for checking that pylance gives no type errors"""
        letters = letter.many()
        number_chars = regex(r"\d").many()
        letters_numbers = letters + number_chars

        assert letters_numbers.parse("ab12") == ["a", "b", "1", "2"]

    def test_add_unaddable_types(self) -> None:
        """
        The type system warns us this isn't possible:

        `Operator "+" not supported for types "Parser[str]" and "Parser[int]"`
        """
        bad_parser = letter + regex(r"\d").map(int)  # type: ignore

        with pytest.raises(TypeError):
            bad_parser.parse("a1")  # type: ignore[unused-ignore]

    def test_add_numerics(self) -> None:
        digit = regex(r"\d")
        numeric_parser = digit.map(float) + digit.map(int)

        assert numeric_parser.parse("12") == 3.0

    def test_seq(self) -> None:
        a = regex("a")
        b = regex("b")
        num = regex(r"[\d]").map(int)

        parser = seq(a, num, b, num, a | num)

        assert parser.parse("a1b2a") == ("a", 1, "b", 2, "a")
        assert parser.parse("a1b23") == ("a", 1, "b", 2, 3)

    def test_add_tuples_like_seq(self) -> None:
        """A possible alternative to `seq`"""
        a = regex("a").tuple()
        b = regex("b").tuple()
        num = regex(r"[\d]").map(int).tuple()

        parser = a + num + b + num + (a | num)

        assert parser.parse("a1b2a") == ("a", 1, "b", 2, "a")
        assert parser.parse("a1b23") == ("a", 1, "b", 2, 3)

    def test_multiply(self) -> None:
        assert (letter * 3).parse("abc") == ["a", "b", "c"]

    def test_multiply_range(self) -> None:
        assert (letter * range(1, 2)).parse("a") == ["a"]
        with pytest.raises(ParseError):
            (letter * range(1, 2)).parse("aa")

    # Primitives

    def test_test_char(self) -> None:
        ascii = gate_char(lambda c: ord(c) < 128).desc("ascii character")
        assert ascii.parse("a") == "a"
        with pytest.raises(ParseError, match="expected 'ascii character' at 0:0"):
            ascii.parse("☺")

        with pytest.raises(ParseError, match="expected 'ascii character' at 0:0"):
            ascii.parse("")

    def test_char_from_str(self) -> None:
        ab = char_from("ab")
        assert ab.parse("a") == "a"
        assert ab.parse("b") == "b"

        with pytest.raises(ParseError, match=re.escape("expected '[ab]' at 0:0")):
            ab.parse("x")

    def test_string_from(self) -> None:
        titles = string_from("Mr", "Mr.", "Mrs", "Mrs.")
        assert titles.parse("Mr") == "Mr"
        assert titles.parse("Mr.") == "Mr."
        assert (titles + string(" Hyde")).parse("Mr. Hyde") == "Mr. Hyde"
        with pytest.raises(
            ParseError,
            match=re.escape("expected one of 'Mr', 'Mr.', 'Mrs', 'Mrs.' at 0:0"),
        ):
            titles.parse("foo")

    def test_peek(self) -> None:
        assert peek(any_char).parse_partial("abc") == ("a", "abc")
        with pytest.raises(ParseError, match="expected 'a digit' at 0:0"):
            peek(digit).parse("a")

    def test_any_char(self) -> None:
        assert any_char.parse("x") == "x"
        assert any_char.parse("\n") == "\n"
        with pytest.raises(ParseError):
            any_char.parse("")

    def test_whitespace(self) -> None:
        assert whitespace.parse("\n") == "\n"
        assert whitespace.parse(" ") == " "
        with pytest.raises(ParseError):
            whitespace.parse("x")

    def test_letter(self) -> None:
        assert letter.parse("a") == "a"
        with pytest.raises(ParseError):
            letter.parse("1")

    def test_digit(self) -> None:
        assert digit.parse("¹") == "¹"
        assert digit.parse("2") == "2"
        with pytest.raises(ParseError):
            digit.parse("x")

    def test_decimal_digit(self) -> None:
        assert decimal_digit.at_least(1).concat().parse("9876543210") == "9876543210"
        with pytest.raises(ParseError):
            decimal_digit.parse("¹")

    def test_should_fail(self) -> None:
        not_a_digit = digit.should_fail("not a digit") >> regex(r".*")

        assert not_a_digit.parse("a") == "a"
        assert not_a_digit.parse("abc") == "abc"
        assert not_a_digit.parse("a10") == "a10"
        assert not_a_digit.parse("") == ""

        with pytest.raises(ParseError, match="expected 'not a digit' at 0:0"):
            not_a_digit.parse("8")

        with pytest.raises(ParseError):
            not_a_digit.parse("8ab")

    def test_should_fail_isolated(self) -> None:
        not_a_digit = digit.should_fail("not a digit")

        assert not_a_digit.parse_partial("a") == (
            Result(
                status=False,
                index=-1,
                value=None,
                furthest=0,
                expected=frozenset({"a digit"}),
            ),
            "a",
        )
        with pytest.raises(ParseError):
            not_a_digit.parse_partial("1")

    def test_from_enum_string(self) -> None:
        class Pet(enum.Enum):
            CAT = "cat"
            DOG = "dog"

        pet = from_enum(Pet)
        assert pet.parse("cat") == Pet.CAT
        assert pet.parse("dog") == Pet.DOG
        with pytest.raises(ParseError):
            pet.parse("foo")

    def test_from_enum_int(self) -> None:
        class Position(enum.Enum):
            FIRST = 1
            SECOND = 2

        position = from_enum(Position)
        assert position.parse("1") == Position.FIRST
        assert position.parse("2") == Position.SECOND
        with pytest.raises(ParseError):
            position.parse("foo")


class TestUtils:
    def test_line_info_at(self) -> None:
        text = "abc\ndef"
        assert line_info_at(ParseState(text, 0)) == (0, 0)
        assert line_info_at(ParseState(text, 2)) == (0, 2)
        assert line_info_at(ParseState(text, 3)) == (0, 3)
        assert line_info_at(ParseState(text, 4)) == (1, 0)
        assert line_info_at(ParseState(text, 7)) == (1, 3)
        with pytest.raises(ValueError):
            line_info_at(ParseState(text, 8))


# Type alias used in test_recursive_parser, has to be defined at module or class level
RT = Union[int, List["RT"]]


def test_recursive_parser() -> None:
    """
    A recursive parser can be defined by using generators.

    The type of the parser has to be explicitly declared with a type alias which
    is also recursively defined using a forward-declaration.

    This works because the generator can refer the target parser before the target
    parser is defined. Then, when defining the parser, it can use `_parser` to
    indirectly refer to itself, creating a recursive parser.
    """
    digits = regex("[0-9]+").map(int)

    @forward_parser
    def _parser() -> Iterator[Parser[RT]]:
        yield parser

    # The explicit type annotation of `Parser[RT]` could be omitted
    parser: Parser[RT] = digits | string("(") >> _parser.sep_by(string(" ")) << string(
        ")"
    )

    result = parser.parse("(0 1 (2 3 (4 5)))")

    assert result == [0, 1, [2, 3, [4, 5]]]
