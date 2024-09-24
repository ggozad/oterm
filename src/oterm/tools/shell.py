import subprocess

from oterm.tools import Parameters, Property, Tool, ToolFunction

ShellTool = Tool(
    type="function",
    function=ToolFunction(
        name="shell",
        description="Function to execute commands in the user's shell and return the output.",
        parameters=Parameters(
            type="object",
            properties={
                "command": Property(
                    type="string", description="The shell command to execute."
                )
            },
            required=["command"],
        ),
    ),
)


def shell_command(command="") -> str:
    return subprocess.run(command, shell=True, capture_output=True).stdout.decode(
        "utf-8"
    )
