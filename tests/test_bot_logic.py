import unittest

from database import Alert
from logic import is_triggered


def make_alert(direction: str, target: float) -> Alert:
    return Alert(1, 1, 1, 1, "bitcoin", target, direction)


class TriggerLogicTest(unittest.TestCase):
    def test_above_triggers_at_or_above_target(self) -> None:
        self.assertTrue(is_triggered(make_alert("above", 100), 100))
        self.assertTrue(is_triggered(make_alert("above", 100), 101))
        self.assertFalse(is_triggered(make_alert("above", 100), 99))

    def test_below_triggers_at_or_below_target(self) -> None:
        self.assertTrue(is_triggered(make_alert("below", 100), 100))
        self.assertTrue(is_triggered(make_alert("below", 100), 99))
        self.assertFalse(is_triggered(make_alert("below", 100), 101))


if __name__ == "__main__":
    unittest.main()
