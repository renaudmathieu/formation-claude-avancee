"""Weather forecast helper, based on the Open-Meteo API (no API key required)."""

import os
from datetime import date, timedelta

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 10


class WeatherError(Exception):
    """The forecast could not be obtained."""


def pick_day(daily: dict, target: date) -> dict:
    """Return the forecast of `target` from an Open-Meteo `daily` block."""
    first_day = date.fromisoformat(daily["time"][0])
    index = (target - first_day).days + 1
    if not 0 <= index < len(daily["time"]):
        raise WeatherError(f"Pas de prévision disponible pour le {target.isoformat()}.")
    return {
        "date": daily["time"][index],
        "temperature_min_c": daily["temperature_2m_min"][index],
        "temperature_max_c": daily["temperature_2m_max"][index],
        "precipitation_probability_pct": daily["precipitation_probability_max"][index],
    }


def simulated_daily(start: date) -> dict:
    """Build a fixed 7-day block, used when the weather service is unavailable."""
    return {
        "time": [(start + timedelta(days=offset)).isoformat() for offset in range(7)],
        "temperature_2m_min": [6, 7, 5, 8, 9, 7, 6],
        "temperature_2m_max": [14, 16, 12, 17, 18, 15, 13],
        "precipitation_probability_max": [10, 60, 80, 20, 5, 30, 40],
    }


def fetch_daily(city: str) -> dict:
    """Fetch the 7-day forecast of a city from Open-Meteo."""
    try:
        places = httpx.get(
            GEOCODING_URL,
            params={"name": city, "count": 1, "language": "fr"},
            timeout=TIMEOUT_SECONDS,
        )
        places.raise_for_status()
        results = places.json().get("results")
        if not results:
            raise WeatherError(f"Ville inconnue : {city}.")
        forecast = httpx.get(
            FORECAST_URL,
            params={
                "latitude": results[0]["latitude"],
                "longitude": results[0]["longitude"],
                "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max",
                "forecast_days": 7,
                "timezone": "auto",
            },
            timeout=TIMEOUT_SECONDS,
        )
        forecast.raise_for_status()
        daily_block = forecast.json()["daily"]
    except (httpx.HTTPError, ValueError) as error:
        # ValueError: a proxy or captive portal can answer with something that is not JSON.
        raise WeatherError(f"Service météo indisponible : {error}") from error
    return daily_block


def get_forecast(city: str, target: date) -> dict:
    """Return the forecast of a city for a given day.

    Set ESCALE_METEO=simule to use fixed data instead of the network.
    """
    is_simulated = os.environ.get("ESCALE_METEO") == "simule"
    daily = simulated_daily(date.today()) if is_simulated else fetch_daily(city)
    return {"city": city, "is_simulated": is_simulated, **pick_day(daily, target)}
