import json

import httpx

from oterm.types import Tool

LocationTool = Tool(
    type="function",
    function=Tool.Function(
        name="current_location",
        description="Function to return the current location, city, region, country, latitude, and longitude.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={},
            required=[],
        ),
    ),
)


async def current_location():

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://ipinfo.io/")
            if response.status_code == 200:
                data = response.json()

                # Extract latitude and longitude from the location information
                city = data.get("city", "N/A")
                region = data.get("region", "N/A")
                country = data.get("country", "N/A")
                loc = data.get("loc", "N/A").split(",")
                if len(loc) == 2:
                    latitude, longitude = float(loc[0]), float(loc[1])
                else:
                    latitude, longitude = None, None

                return json.dumps(
                    {
                        "city": city,
                        "region": region,
                        "country": country,
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                )
            else:
                return json.dumps(
                    {"error": f"{response.status_code}: {response.reason_phrase}"}
                )
        except httpx.HTTPError as e:
            return json.dumps({"error": str(e)})
