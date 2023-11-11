from dataclasses import dataclass
from typing import List

from parsy import gather, regex, string, take

# Create a parser for the following text and then run it and see the results

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
    number: int
    name: str
    score: int


@dataclass
class GradeRaw:
    grade: int = take(string("Grade = ") >> integer << string("\n"))
    students: List[Student] = take(
        string("Student number, Name\n") >> gather(Student).many() << regex(r"\n*")
    )
    scores: List[Score] = take(
        string("Student number, Score\n") >> gather(Score).many() << regex(r"\n*")
    )


@dataclass
class Grade:
    """Grade data in a more useful format than what's in the raw text."""

    grade: int
    student_scores: List[StudentWithScore]

    @staticmethod
    def from_raw_grade(grade: GradeRaw) -> "Grade":
        """Transform from the raw grade structure into something more useful."""
        students = {student.number: student.name for student in grade.students}

        student_scores = [
            StudentWithScore(score.number, students[score.number], score.score)
            for score in grade.scores
        ]

        return Grade(grade.grade, student_scores)


@dataclass
class School:
    name: str = take(string("School = ") >> any_text << string("\n"))
    # Note that we map from GradeRaw to a more useful transformed Grade structure
    grades: List[Grade] = take(gather(GradeRaw).map(Grade.from_raw_grade).many())


@dataclass
class File:
    header: str = take(regex(r"[\s\S]*?(?=School =)"))
    schools: List[School] = take(gather(School).many())


def test_combined_dataclass_demo() -> None:
    file = gather(File).parse(text)

    assert file.schools == [
        School(
            name="Riverdale High",
            grades=[
                Grade(
                    grade=1,
                    student_scores=[
                        StudentWithScore(number=0, name="Phoebe", score=3),
                        StudentWithScore(number=1, name="Rachel", score=7),
                    ],
                ),
                Grade(
                    grade=2,
                    student_scores=[
                        StudentWithScore(number=0, name="Angela", score=6),
                        StudentWithScore(number=1, name="Tristan", score=3),
                        StudentWithScore(number=2, name="Aurora", score=9),
                    ],
                ),
            ],
        ),
        School(
            name="Hogwarts",
            grades=[
                Grade(
                    grade=1,
                    student_scores=[
                        StudentWithScore(number=0, name="Ginny", score=8),
                        StudentWithScore(number=1, name="Luna", score=7),
                    ],
                ),
                Grade(
                    grade=2,
                    student_scores=[
                        StudentWithScore(number=0, name="Harry", score=5),
                        StudentWithScore(number=1, name="Hermione", score=10),
                    ],
                ),
                Grade(
                    grade=3,
                    student_scores=[
                        StudentWithScore(number=0, name="Fred", score=0),
                        StudentWithScore(number=1, name="George", score=0),
                    ],
                ),
            ],
        ),
    ]
