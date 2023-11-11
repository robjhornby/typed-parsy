# Typed Parsy

This is an experiment to create a parser combinator library with complete type annotations.

It now fully passes Pylance (strict) and mypy (strict).

This is a modified version of [Parsy](https://parsy.readthedocs.io/en/latest/overview.html),
with certain features removed and replaced to allow for complete type annotations.
Here are the main changes:

* Introduced dataclass parsers. Parsers are assigned as metadata in fields of a
  dataclass by using the ``take`` field descriptor. Then ``gather`` is used to
  combine all field parsers of the dataclass into
  a single parser that sequentially calls each field parser and returns a dataclass
  instance as a result, with each field populated by the result of its associated parser.
  There are examples of this in the examples folder.
* The ``seq`` function is now positional-only and creates a parser with a Tuple result.
  These tuple results are unpacked when using the `.combine` method and passed as the
  arguments to the target function. This allows type checkers to detect any mismatches
  between the parser's result tuple and the function's arguments, catching errors early.
* The keyword version of ``seq`` was removed and
  replaced by dataclass parsers which fill the same need. The ``.combine_dict`` function
  was also removed for the same reason.
* There are more parsers and combinators for Tuple results, because
  tuples are convenient for keeping track of the combined parser result types.
  You can ``.join`` a parser to another parser to create a combined parser with a 2-tuple
  result. You can then ``.append`` another parser to append its result to the end of the
  tuple. This new parser will return a 3-tuple result, with the type of each element known
  to type checkers. This can be used with ``.combine``, same as a ``seq`` parser.


The docs have not been updated, see the source code and examples folder.

## Installation

Clone the repo and install it with [poetry](https://python-poetry.org/) by running
`poetry install`.

Then head to the examples folder, starting with `dataclass_parsing.py` for the star feature,
and `dataclass_parser_demo.py` for a larger example.
