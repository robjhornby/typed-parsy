from dataclasses import dataclass

from parsy import gather, regex, string, take


def test_default_group() -> None:
    # Default group is 0 (everything)
    default = regex(r"abc")
    assert default.parse("abc") == "abc"


def test_int_group() -> None:
    # Use a group specified by an int
    int_group = regex(r"ab(c)", group=1)
    assert int_group.parse("abc") == "c"


def test_named_group() -> None:
    # Use a group specified by a string (using named capture groups)
    named_group = regex(r"ab(?P<target>c)", group="target")
    assert named_group.parse("abc") == "c"


def test_tuple_int_groups() -> None:
    # Use multiple groups specified by a tuple of ints
    tuple_int_groups = regex(r"a(b)(c)", group=(1, 2))
    assert tuple_int_groups.parse("abc") == ("b", "c")


def test_singleton_tuple_group() -> None:
    # Use a 1-tuple group. Python's `re` module treats a 1-tuple group the same as a single integer group
    # meaning the result is just the string which matched, not wrapped in a tuple. Parsy's `regex` does the same.
    tuple_int_singleton = regex(r"a(b)", group=(1,))
    assert tuple_int_singleton.parse("ab") == "b"


def test_tuple_named_groups() -> None:
    # Use multiple groups specified by a tuple of named capture groups
    tuple_int_groups = regex(r"a(?P<first>b)(?P<second>c)", group=("first", "second"))
    assert tuple_int_groups.parse("abc") == ("b", "c")


def test_mixed_named_int_groups() -> None:
    # Groups specified by both ints and named groups
    mixed_groups = regex(r"a(?P<first>b)(?P<second>c)", group=("first", 2))
    assert mixed_groups.parse("abc") == ("b", "c")


def test_combine_groups_with_function() -> None:
    # Combining with more
    parser = regex(
        r"(?P<ID>\d+): (?P<first>\d+) \+ (?P<second>\d+)",
        group=("ID", "first", "second"),
    )
    mapped_parser = parser.combine(
        lambda id, first, second: {id: int(first) + int(second)}
    )

    assert mapped_parser.parse("123: 3 + 4") == {"123": 7}


def test_regex_parsers_in_dataclass() -> None:
    # Build up regex parsers in a dataclass then use them in another parser
    digits = regex(r"[\d]+")

    @dataclass
    class Sum:
        id: str = take(digits << string(": "))
        first: int = take(digits.map(int) << string(" + "))
        second: int = take(digits.map(int))

    parser = gather(Sum)
    mapped_parser = parser.map(lambda res: {res.id: res.first + res.second})
    assert mapped_parser.parse("123: 3 + 4") == {"123": 7}
