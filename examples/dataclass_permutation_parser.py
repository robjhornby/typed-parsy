from dataclasses import dataclass

from parsy import dataclass_permutation_parser, eof, regex, take, whitespace


def test_permutation_parser():
    @dataclass
    class Person:
        name: str = take(regex(r"[a-zA-Z]+") << (whitespace | eof).desc("name"))
        age: int = take(regex(r"\d+").map(int).desc("An integer age") << (whitespace | eof))
        id: str = take(regex(r"\d{3}-\d{3}") << (whitespace | eof))

    person_parser = dataclass_permutation_parser(Person)

    person = person_parser.parse("Rob 2000 123-456")
    person_b = person_parser.parse("123-456 2000 Rob")
    print(person)
    print(person_b)
    assert person == person_b
