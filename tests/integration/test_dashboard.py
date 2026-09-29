"""Browserless integration coverage for the Streamlit entrypoint."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_analyzes_the_built_in_example() -> None:
    app = AppTest.from_file(Path(__file__).parents[2] / "dashboard" / "app.py")

    app.run()
    app.button[0].click().run()

    assert not app.exception
    assert app.title[0].value == "TraceLens"
    assert app.metric[0].value == "10"
    assert any(heading.value == "Timeline" for heading in app.subheader)
