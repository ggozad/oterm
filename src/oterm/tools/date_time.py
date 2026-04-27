from datetime import datetime


def date_time() -> str:
    """Get the current date and time in ISO format."""
    return datetime.now().isoformat()
