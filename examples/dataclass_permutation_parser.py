from dataclasses import dataclass

from parsy import eof, gather_perm, regex, take, whitespace


def test_permutation_parser() -> None:
    @dataclass
    class Person:
        name: str = take(regex(r"[a-zA-Z]+") << (whitespace | eof).desc("name"))
        age: int = take(
            regex(r"\d+").map(int).desc("An integer age") << (whitespace | eof)
        )
        id: str = take(regex(r"\d{3}-\d{3}") << (whitespace | eof))

    person_parser = gather_perm(Person)

    person = person_parser.parse("Frodo 2000 123-456")
    person_b = person_parser.parse("123-456 2000 Frodo")
    print(person)
    print(person_b)
    assert person == person_b
