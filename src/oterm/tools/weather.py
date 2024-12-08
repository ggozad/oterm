import json

import httpx

from oterm.config import envConfig
from oterm.types import Tool

WeatherTool = Tool(
    type="function",
    function=Tool.Function(
        name="current_weather",
        description="Function to return the current weather for the given location in Standard Units.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={
                "latitude": Tool.Function.Parameters.Property(
                    type="float", description="The latitude of the location."
                ),
                "longitude": Tool.Function.Parameters.Property(
                    type="float", description="The longitude of the location."
                ),
            },
            required=["latitude", "longitude"],
        ),
    ),
)


async def current_weather(latitude: float, longitude: float) -> str:
    async with httpx.AsyncClient() as client:
        try:
            api_key = envConfig.OPEN_WEATHER_MAP_API_KEY
            if not api_key:
                raise Exception("OpenWeatherMap API key not found")

            response = await client.get(
                f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}"
            )

            if response.status_code == 200:
                data = response.json()
                return json.dumps(data)
            else:
                return json.dumps(
                    {"error": f"{response.status_code}: {response.reason_phrase}"}
                )
        except Exception as e:
            return json.dumps({"error": str(e)})
