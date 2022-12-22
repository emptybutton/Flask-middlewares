from typing import Callable, Iterable

from flask import redirect, url_for
from werkzeug.routing import BuildError

from flask_middlewares import Middleware
from flask_middlewares.tools import get_status_code_from


class StatusCodeAbortingMiddleware(Middleware):
    """
    Middleware class that implements the abort of some status code (by default
    it's 400 ~ 500) exiting the router.
    """

    def __init__(
        self,
        status_codes_to_abort: Iterable[int] = range(400, 501),
        *,
        status_code_reponse_parser: Callable[[any], int] = get_status_code_from,
        aborter: Callable[[int], any] = abort
    ):
        self.status_codes_to_abort = status_codes_to_abort
        self.status_code_reponse_parser = status_code_reponse_parser
        self.aborter = aborter

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        response = route(*args, **kwargs)
        status_code = self.status_code_reponse_parser(response)

        return (
            self.aborter(status_code)
            if status_code in self.status_codes_to_abort
            else response
        )


class StatusCodeRedirectorMiddleware(Middleware):
    """
    Middleware class that implements a redirect to some endpoint by some values
    of a status code of Flask Response returned from the router.

    Specifies the URL of the endpoint by the redirect_resource attribute, which
    can represent both the URL itself and the name of the view function
    processed by this URL.

    Defines the transition on the status codes of the response corresponding to
    the value / values of the status codes contained in the status_codes
    attribute.
    """

    def __init__(self, redirect_resource: str, status_codes: Iterable[int] | int = (301, 302)):
        self.redirect_resource = redirect_resource
        self.status_codes = (
            tuple(status_codes)
            if isinstance(status_codes, Iterable)
            else (status_codes, )
        )

    @property
    def redirect_url(self) -> str:
        """Structural endpoint property for redirection."""

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