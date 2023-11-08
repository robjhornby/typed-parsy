from dataclasses import dataclass
from typing import Optional

from parsy import gather, regex, string, take, whitespace


@dataclass
class Person:
    name: str = take(regex(r"\w+") << whitespace)
    age: int = take(regex(r"\d+").map(int) << whitespace)
    note: str = take(regex(".+"))


def test_dataclass_parser() -> None:
    person_parser = gather(Person)
    person = person_parser.parse("Frodo 2000 how time flies")
    assert person == Person(name="Frodo", age=2000, note="how time flies")


# Nesting dataclass parsers


@dataclass
class Id:
    id: str = take(regex(r"[^\s]+") << whitespace.optional())
    from_year: Optional[int] = take(
        regex("[0-9]+").map(int).desc("Numeric").optional() << whitespace.optional()
    )


@dataclass
class Name:
    name: str = take(regex(r"[a-zA-Z]+") << whitespace.optional())
    abbreviated: Optional[bool] = take(
        (string("T").result(True) | string("F").result(False)).optional()
        << whitespace.optional()
    )


@dataclass
class PersonDetail:
    id: Id = take(gather(Id))
    forename: Name = take(gather(Name))
    surname: Optional[Name] = take(gather(Name).optional())


def test_dataclass_parser_with_optional_field() -> None:
    out_parser = gather(PersonDetail).many()

    new_person = out_parser.parse("007 2023 Frodo T John 123 2004 Bob")

    res = [
        PersonDetail(
            id=Id(id="007", from_year=2023),
            forename=Name(name="Frodo", abbreviated=True),
            surname=Name(name="John", abbreviated=None),
        ),
        PersonDetail(
            id=Id(id="123", from_year=2004),
            forename=Name(name="Bob", abbreviated=None),
            surname=None,
        ),
    ]
    assert new_person == res


# Dataclass parsing where not all fields have a parsy parser


@dataclass
class PersonWithRarity:
    name: str = take(regex(r"\w+") << whitespace)
    age: int = take(regex(r"\d+").map(int) << whitespace)
    note: str = take(regex(".+"))
    rare: bool = False

    def __post_init__(self) -> None:
        if self.age > 70:
            self.rare = True


def test_dataclass_with_default_value() -> None:
    parser = gather(PersonWithRarity)
    person = parser.parse("Frodo 20 whippersnapper")
    assert person == PersonWithRarity(
        name="Frodo", age=20, note="whippersnapper", rare=False
    )

    person = parser.parse("Frodo 2000 how time flies")
    assert person == PersonWithRarity(
        name="Frodo", age=2000, note="how time flies", rare=True
    )
