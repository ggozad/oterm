from ollama import Tool

OracleTool = Tool(
    type="function",
    function=Tool.Function(
        name="oracle",
        description="Function to return the Oracle's answer to any question.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={
                "question": Tool.Function.Parameters.Property(
                    type="str", description="The question to ask."
                ),
            },
            required=["question"],
        ),
    ),
)


def oracle(question: str):
    return "oterm"
