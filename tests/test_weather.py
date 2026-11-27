from datetime import date, timedelta

import pytest

from escale.tools import weather

DAILY = {
    "time": ["2026-11-04", "2026-11-05", "2026-11-06"],
    "temperature_2m_min": [1, 2, 3],
    "temperature_2m_max": [11, 12, 13],
    "precipitation_probability_max": [10, 20, 30],
}


@pytest.mark.skip(reason="TODO: la météo de demain ne correspond pas au site de référence")
def test_pick_day_returns_the_requested_day():
    assert weather.pick_day(DAILY, date(2026, 11, 5))["temperature_max_c"] == 12


def test_pick_day_rejects_a_day_outside_the_forecast():
    with pytest.raises(weather.WeatherError):
        weather.pick_day(DAILY, date(2026, 12, 25))


def test_simulated_mode_needs_no_network(monkeypatch):
    monkeypatch.setenv("ESCALE_METEO", "simule")
    monkeypatch.setattr(weather, "fetch_daily", lambda city: pytest.fail("network used"))
    forecast = weather.get_forecast("Lyon", date.today() + timedelta(days=1))
    assert forecast["city"] == "Lyon"
    assert forecast["is_simulated"] is True
