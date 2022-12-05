from typing import Callable, Iterable

from flask_middlewares import Middleware
from flask_middlewares.tools import get_status_code_from


class AbortBadStatusCodeMiddleware(Middleware):
    def call_route(self, route: Callable, *args, **kwargs) -> any:
        response = route(*args, **kwargs)

        status_code = get_status_code_from(response)

        if 400 <= status_code <= 500:
            abort(status_code)

        return response


class StatusCodeRedirectorMiddleware(Middleware):
    def __init__(self, redirect_resource: str, status_codes: Iterable[int] | int):
        self.redirect_resource = redirect_resource
        self.status_codes = (
            tuple(status_codes)
            if isinstance(status_codes, Iterable)
            else (status_codes, )
        )

    @property
    def redirect_url(self) -> str:
        try:
            return url_for(self.redirect_resource)
        except BuildError:
            return self.redirect_resource

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        response = route(*args, **kwargs)

        return (
            redirect(self.redirect_url)
            if get_status_code_from(response) in self.status_codes
            else response
        )