import tempfile
import unittest
from pathlib import Path

from database import AlertRepository


class AlertRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = str(Path(self.temp_directory.name) / "test.db")
        self.repository = AlertRepository(database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_add_list_and_delete_alert(self) -> None:
        alert_id = self.repository.add_alert(
            guild_id=1,
            channel_id=2,
            user_id=3,
            coin_id="Bitcoin",
            target_price=100_000,
            direction="above",
        )

        alerts = self.repository.list_alerts(guild_id=1, user_id=3)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].id, alert_id)
        self.assertEqual(alerts[0].coin_id, "bitcoin")
        self.assertTrue(
            self.repository.delete_alert(alert_id=alert_id, guild_id=1, user_id=3)
        )
        self.assertEqual(self.repository.list_alerts(guild_id=1, user_id=3), [])

    def test_user_cannot_delete_another_users_alert(self) -> None:
        alert_id = self.repository.add_alert(
            guild_id=1,
            channel_id=2,
            user_id=3,
            coin_id="ethereum",
            target_price=5_000,
            direction="below",
        )
        self.assertFalse(
            self.repository.delete_alert(alert_id=alert_id, guild_id=1, user_id=999)
        )

    def test_invalid_direction_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.add_alert(
                guild_id=1,
                channel_id=2,
                user_id=3,
                coin_id="bitcoin",
                target_price=1,
                direction="sideways",
            )


if __name__ == "__main__":
    unittest.main()
