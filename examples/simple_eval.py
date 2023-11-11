from typing import Iterator, Union

from parsy import (
    Parser,
    ParseState,
    Result,
    forward_parser,
    regex,
    string,
    success,
)

"""
nonZeroDigit = "1"|"2"|"3"|"4"|"5"|"6"|"7"|"8"|"9";
digit = "0" | nonZeroDigit;
naturalNumber = nonZeroDigit , {digit};
secondPriorityOperators= "+" |"-";
firstPriorityOperators= "*" | "/";
syntax=expr;
expr=term, {secondPriorityOperators, term};
term=factor, {firstPriorityOperators, factor};
factor="(", expr , ")" | naturalNumber;
root = "#" , root | factor;
power = root, "^" , power| root;
"""


whitespace = regex(r"\s*")
integer = regex(r"\s*(\d+)\s*", group=1).map(int)
float_ = regex(r"\s*(\d+\.\d+)\s*", group=1).map(float)
plus = string("+").result(1)
minus = string("-").result(-1)


def simple_eval(tokens: str) -> Union[int, float]:
    # This function parses and evaluates at the same time.

    # _simple = forward_parser(lambda: (yield simple))
    @forward_parser
    def _simple() -> Iterator[Parser[Union[int, float]]]:
        yield simple

    @forward_parser
    def _multiplicative() -> Iterator[Parser[Union[int, float]]]:
        yield multiplicative

    @Parser
    def additive(s: ParseState) -> Result[Union[int, float]]:
        res, s = s.apply(_multiplicative)
        sign_parser = whitespace >> (plus | minus) << whitespace
        while True:
            sign, s = s.apply(sign_parser.optional())
            if sign is None:
                break
            operand, s = s.apply(_multiplicative)
            res += sign * operand
        return s.success(res)

    @Parser
    def multiplicative(s: ParseState) -> Result[Union[int, float]]:
        res, s = s.apply(_simple)
        op = whitespace >> (string("*") | string("/")) << whitespace
        while True:
            operation, s = s.apply(op | success(""))
            if not operation:
                break
            operand, s = s.apply(_simple)
            if operation == "*":
                res *= operand
            elif operation == "/":
                res /= operand
        return s.success(res)

    @Parser
    def number(s: ParseState) -> Result[Union[int, float]]:
        sign, s = s.apply(whitespace >> (plus | minus | success(1)))
        value, s = s.apply(float_ | integer)
        return s.success(sign * value)

    lparen = string("(")
    rparen = string(")")

    expr = additive
    simple = (lparen >> expr << rparen) | number

    return expr.parse(tokens)


def test_simple_expression() -> None:
    assert simple_eval("((1 + 2) * 3 - 3) / 2") == 3
