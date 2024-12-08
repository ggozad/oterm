import subprocess

from oterm.types import Tool

ShellTool = Tool(
    type="function",
    function=Tool.Function(
        name="shell",
        description="Function to execute commands in the user's shell and return the output.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={
                "command": Tool.Function.Parameters.Property(
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
