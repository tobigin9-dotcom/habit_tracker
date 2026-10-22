from datetime import time

import pytest
from pydantic import ValidationError

from app.schemas import HabitCreate


def test_habit_create_trims_name():
    habit = HabitCreate(name="  Read  ", reminder_time=time(20, 0))
    assert habit.name == "Read"


def test_habit_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        HabitCreate(name=" ", reminder_time=time(20, 0))


def test_habit_target_must_be_positive():
    with pytest.raises(ValidationError):
        HabitCreate(
            name="Read",
            target_completions=0,
            reminder_time=time(20, 0),
            )
