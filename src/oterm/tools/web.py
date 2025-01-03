import json
from html.parser import HTMLParser

import httpx

from oterm.types import Tool

WebTool = Tool(
    type="function",
    function=Tool.Function(
        name="fetch_url",
        description="Function to return the contents of a website in text format.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={
                "url": Tool.Function.Parameters.Property(
                    type="str", description="The URL of the website to fetch."
                ),
            },
            required=["url"],
        ),
    ),
)


class HTML2Text(HTMLParser):
    text = ""

    def handle_data(self, data):
        self.text += data


async def fetch_url(url: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)

            if response.status_code == 200:
                html = response.text
                parser = HTML2Text()
                parser.feed(html)
                return parser.text

            else:
                return json.dumps(
                    {
                        "error": f"Failed to fetch URL: {url}. Status code: {response.status_code}"
                    }
                )
        except Exception as e:
            return json.dumps({"error": str(e)})
