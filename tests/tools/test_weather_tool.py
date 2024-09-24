import json

import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.location import LocationTool, current_location
from oterm.tools.weather import WeatherTool, current_weather


@pytest.mark.asyncio
async def test_weather():
    llm = OllamaLLM(
        tool_defs=[
            {"tool": WeatherTool, "callable": current_weather},
        ],
    )
    weather = json.loads(await current_weather(latitude=59.2675, longitude=10.4076))
    temperature = weather.get("main").get("temp") - 273.15

    res = await llm.completion(
        "What is the current temperature at my location latitude 59.2675, longitude 10.4076?"
    )

    assert "temperature" in res or "Temperature" in res
    assert str(round(temperature)) in res or str(round(temperature, 1)) in res


@pytest.mark.asyncio
async def test_weather_with_location():
    llm = OllamaLLM(
        tool_defs=[
            {"tool": LocationTool, "callable": current_location},
            {"tool": WeatherTool, "callable": current_weather},
        ],
    )
    location = json.loads(await current_location())
    weather = json.loads(
        await current_weather(
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
        )
    )
    temperature = weather.get("main").get("temp") - 273.15

    res = await llm.completion("What is the current temperature in my city?")
    assert "temperature" in res or "Temperature" in res
    assert str(round(temperature)) in res or str(round(temperature, 1)) in res
