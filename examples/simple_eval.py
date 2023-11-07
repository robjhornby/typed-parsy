from typing import Iterator, Union

from parsy import Parser, ParseState, Result, forward_parser, match_char, regex, success

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
plus = match_char("+").result(1)
minus = match_char("-").result(-1)


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
        sign = whitespace >> (match_char("+") | match_char("-")) << whitespace
        while True:
            operation, s = s.apply(sign | success(""))
            if not operation:
                break
            operand, s = s.apply(_multiplicative)
            if operation == "+":
                res += operand
            elif operation == "-":
                res -= operand
        return s.success(res)

    @Parser
    def multiplicative(s: ParseState) -> Result[Union[int, float]]:
        res, s = s.apply(_simple)
        op = whitespace >> (match_char("*") | match_char("/")) << whitespace
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

    lparen = match_char("(")
    rparen = match_char(")")

    expr = additive
    simple = (lparen >> expr << rparen) | number

    return expr.parse(tokens)


if __name__ == "__main__":
    print(simple_eval("((1 + 2) * 3 - 3)"))
