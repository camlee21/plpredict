import re

from django.core.exceptions import ValidationError

# Mirrors Gmail's own username rules (letters, numbers, periods; no leading,
# trailing or doubled periods), just capped at 16 characters instead of 30.
USERNAME_MAX_LENGTH = 16
_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.]{0,14}[A-Za-z0-9])?$")


def validate_username_format(value):
    if not _USERNAME_RE.match(value) or ".." in value:
        raise ValidationError(
            "Usernames can only contain letters, numbers and periods (no spaces or "
            f"other symbols), must start and end with a letter or number, and be at "
            f"most {USERNAME_MAX_LENGTH} characters."
        )
