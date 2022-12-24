from typing import Callable, Iterable, Container

from flask import abort

from flask_middlewares import Middleware
from flask_middlewares.tools import get_status_code_from, redirect_by


class StatusCodeAbortingMiddleware(Middleware):
    """
    Middleware class that implements the abort of some status code (by default
    it's 400 ~ 500) exiting the router.
    """

    def __init__(
        self,
        status_code_resource_to_abort: Iterable[int] | int = range(400, 501),
        *,
        status_code_reponse_parser: Callable[[any], int] = get_status_code_from,
        aborter: Callable[[int], any] = abort
    ):
        self.status_code_reponse_parser = status_code_reponse_parser
        self.aborter = aborter
        self.status_codes_to_abort = (
            status_code_resource_to_abort
            if isinstance(status_code_resource_to_abort, Iterable)
            else (status_code_resource_to_abort, )
        )

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
    of a status code of a response returned from the router.

    Specifies the URL of the endpoint by the redirect_resource attribute, which
    can represent both the URL itself and, if redirect_resource is default, the
    name of the view function processed by this URL.

    Defines the transition on the status codes of the response corresponding to
    the value / values of the status codes contained in the status_codes
    attribute.
    """

    def __init__(
        self,
        redirect_url: str,
        status_code_resource: Container[int] | int,
        *,
        status_code_parser: Callable[[any], int] = get_status_code_from,
        url_redirector: Callable[[str], any] = redirect_by,
    ):
        self.status_code_parser = status_code_parser
        self.url_redirector = url_redirector

        self.redirect_url = redirect_url
        self.status_codes = (
            status_code_resource
            if isinstance(status_code_resource, Container)
            else (status_code_resource, )
        )

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        response = route(*args, **kwargs)

        return (
            self.url_redirector(self.redirect_url)
            if self.status_code_parser(response) in self.status_codes
            else response
        )