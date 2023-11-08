from dataclasses import dataclass
from typing import List

from parsy import gather, regex, string, take

text = """Sample text

A selection of students from Riverdale High and Hogwarts took part in a quiz. This is a record of their scores.

School = Riverdale High
Grade = 1
Student number, Name
0, Phoebe
1, Rachel

Student number, Score
0, 3
1, 7

Grade = 2
Student number, Name
0, Angela
1, Tristan
2, Aurora

Student number, Score
0, 6
1, 3
2, 9

School = Hogwarts
Grade = 1
Student number, Name
0, Ginny
1, Luna

Student number, Score
0, 8
1, 7

Grade = 2
Student number, Name
0, Harry
1, Hermione

Student number, Score
0, 5
1, 10

Grade = 3
Student number, Name
0, Fred
1, George

Student number, Score
0, 0
1, 0
"""


integer = regex(r"\d+").map(int)
any_text = regex(r"[^\n]+")


@dataclass
class Student:
    number: int = take(integer << string(", "))
    name: str = take(any_text << string("\n"))


@dataclass
class Score:
    number: int = take(integer << string(", "))
    score: int = take(integer << string("\n"))


@dataclass
class StudentWithScore:
    name: str
    number: int
    score: int


@dataclass
class Grade:
    grade: int = take(string("Grade = ") >> integer << string("\n"))
    students: List[Student] = take(
        string("Student number, Name\n") >> gather(Student).many() << regex(r"\n*")
    )
    scores: List[Score] = take(
        string("Student number, Score\n") >> gather(Score).many() << regex(r"\n*")
    )


@dataclass
class School:
    name: str = take(string("School = ") >> any_text << string("\n"))
    grades: List[Grade] = take(gather(Grade).many())


@dataclass
class File:
    header: str = take(regex(r"[\s\S]*?(?=School =)"))
    schools: List[School] = take(gather(School).many())


if __name__ == "__main__":
    file = gather(File).parse(text)
    print(file.schools)
    assert file.schools == [
        School(
            name="Riverdale High",
            grades=[
                Grade(
                    grade=1,
                    students=[
                        Student(number=0, name="Phoebe"),
                        Student(number=1, name="Rachel"),
                    ],
                    scores=[Score(number=0, score=3), Score(number=1, score=7)],
                ),
                Grade(
                    grade=2,
                    students=[
                        Student(number=0, name="Angela"),
                        Student(number=1, name="Tristan"),
                        Student(number=2, name="Aurora"),
                    ],
                    scores=[
                        Score(number=0, score=6),
                        Score(number=1, score=3),
                        Score(number=2, score=9),
                    ],
                ),
            ],
        ),
        School(
            name="Hogwarts",
            grades=[
                Grade(
                    grade=1,
                    students=[
                        Student(number=0, name="Ginny"),
                        Student(number=1, name="Luna"),
                    ],
                    scores=[Score(number=0, score=8), Score(number=1, score=7)],
                ),
                Grade(
                    grade=2,
                    students=[
                        Student(number=0, name="Harry"),
                        Student(number=1, name="Hermione"),
                    ],
                    scores=[Score(number=0, score=5), Score(number=1, score=10)],
                ),
                Grade(
                    grade=3,
                    students=[
                        Student(number=0, name="Fred"),
                        Student(number=1, name="George"),
                    ],
                    scores=[Score(number=0, score=0), Score(number=1, score=0)],
                ),
            ],
        ),
    ]
