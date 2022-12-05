from typing import Iterable, Optional, Self, Callable

from beautiful_repr import StylizedMixin, Field, TemplateFormatter
from flask import Response


def get_status_code_from(response: any) -> int:
    if isinstance(response, Response):
        return response.status_code
    elif (
        isinstance(response, Iterable)
        and len(response) >= 2
        and isinstance(response[1], int | float)
        and int(response[1]) == response[1]
        and 400 <= response[1] <= 500
    ):
        return response[1]
    else:
        return 200
