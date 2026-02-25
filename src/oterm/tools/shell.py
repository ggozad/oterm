import subprocess


def shell(command: str) -> str:
    """Execute a command in the user's shell and return the output.

    Args:
        command: The shell command to execute.
    """
    return subprocess.run(command, shell=True, capture_output=True).stdout.decode(
        "utf-8"
    )
