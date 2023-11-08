from dataclasses import dataclass

from parsy import gather, regex, string, take

# Default group is 0 (everything)
default = regex(r"abc")
assert default.parse("abc") == "abc"

# Use a group specified by an int
int_group = regex(r"ab(c)", group=1)
assert int_group.parse("abc") == "c"

# Use a group specified by a string (using named capture groups)
named_group = regex(r"ab(?P<target>c)", group="target")
assert named_group.parse("abc") == "c"

# Use multiple groups specified by a tuple of ints
tuple_int_groups = regex(r"a(b)(c)", group=(1, 2))
assert tuple_int_groups.parse("abc") == ("b", "c")

# Use a 1-tuple group. Python's `re` module treats a 1-tuple group the same as a single integer group
# meaning the result is just the string which matched, not wrapped in a tuple. Parsy's `regex` does the same.
tuple_int_singleton = regex(r"a(b)", group=(1,))
assert tuple_int_singleton.parse("ab") == "b"


# Use multiple groups specified by a tuple of named capture groups
tuple_int_groups = regex(r"a(?P<first>b)(?P<second>c)", group=("first", "second"))
assert tuple_int_groups.parse("abc") == ("b", "c")


# Groups specified by both ints and named groups
mixed_groups = regex(r"a(?P<first>b)(?P<second>c)", group=("first", 2))
assert mixed_groups.parse("abc") == ("b", "c")

# Combining with more
parser = regex(
    r"(?P<ID>\d+): (?P<first>\d+) \+ (?P<second>\d+)", group=("ID", "first", "second")
)
mapped_parser = parser.combine(lambda id, first, second: {id: int(first) + int(second)})

assert mapped_parser.parse("123: 3 + 4") == {"123": 7}

# The same example again, using a dataclass to structure the parsing result
digits = regex(r"[\d]+")


@dataclass
class Sum:
    id: str = take(digits << string(": "))
    first: int = take(digits.map(int) << string(" + "))
    second: int = take(digits.map(int))


d_parser = gather(Sum)
d_mapped_parser = d_parser.map(lambda res: {res.id: res.first + res.second})
assert d_mapped_parser.parse("123: 3 + 4") == {"123": 7}
