import unittest

from streamlit.testing.v1 import AppTest


class StreamlitSmokeTests(unittest.TestCase):
    def test_settings_view_starts_without_runtime_errors(self) -> None:
        app = AppTest.from_file("app.py", default_timeout=45)
        app.query_params["view"] = "settings"
        app.run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(len(app.toggle), 1)
        self.assertEqual(app.toggle[0].label, "데모 데이터 표시")

    def test_query_parameter_change_updates_existing_view_widget(self) -> None:
        app = AppTest.from_file("app.py", default_timeout=45)
        app.query_params["view"] = "settings"
        app.run()
        self.assertEqual(app.segmented_control[0].value, "설정")

        app.query_params["view"] = "alpha-discovery"
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.segmented_control[0].value, "알파 후보 탐색")
        self.assertEqual(app.query_params["view"], ["alpha-discovery"])

    def test_demo_preference_survives_view_round_trip(self) -> None:
        app = AppTest.from_file("app.py", default_timeout=45)
        app.query_params["view"] = "settings"
        app.run()
        app.toggle[0].set_value(True).run()
        self.assertTrue(app.session_state["demo_mode_preference"])

        app.query_params["view"] = "macro"
        app.run()
        app.query_params["view"] = "settings"
        app.run()

        self.assertTrue(app.toggle[0].value)
        self.assertTrue(app.session_state["demo_mode_preference"])


if __name__ == "__main__":
    unittest.main()
