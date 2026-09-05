from better_profanity import profanity
from django.core.exceptions import ValidationError


def validate_no_profanity(value):
    if profanity.contains_profanity(value):
        raise ValidationError("League name contains inappropriate language.")
