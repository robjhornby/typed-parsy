"""
Stripped down logo lexer, for tokenizing Turtle Logo programs like:

   fd 1
   bk 2
   rt 90

etc.
"""

from dataclasses import dataclass

from parsy import eof, gather, regex, string, string_from, take, whitespace

command = string_from("fd", "bk", "rt", "lt")
number = regex(r"[0-9]+").map(int)
optional_whitespace = regex(r"\s*")
eol = string("\n")
line = (optional_whitespace >> command).pair(whitespace >> number) << (
    eof | eol | (whitespace >> eol)
)
lexer = line.many()


def test_lexer() -> None:
    assert lexer.parse(
        """fd 1
bk 2
"""
    ) == [("fd", 1), ("bk", 2)]


"""
Alternative which creates a more structured output
"""


@dataclass
class Instruction:
    command: str = take(optional_whitespace >> command)
    distance: int = take(whitespace >> number << (eof | eol | (whitespace >> eol)))


instruction_parser = gather(Instruction).many()

assert instruction_parser.parse(
    """fd 1
bk 2
"""
) == [Instruction("fd", 1), Instruction("bk", 2)]
