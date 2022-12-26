from abc import ABC, abstractmethod
from typing import NewType, Callable, Iterable
from functools import cached_property

from flask_middlewares import Middleware
from flask_middlewares.tools import MultipleHandler


ErrorHandler = NewType('ErrorHandler', Callable[[Exception], any])


class ErrorHandlingMiddleware(Middleware, ABC):
    """Middleware class that handles errors that occurred in routers."""

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        try:
            return route(*args, **kwargs)
        except Exception as error:
            return self._handle_error(error)

    @abstractmethod
    def _handle_error(self, error: Exception) -> any:
        """Method that implements response to an error that has occurred."""


class ErrorHandlerMiddleware(ErrorHandlingMiddleware, ABC):
    """
    ErrorHandlingMiddleware delegating error handling to error handlers.

    Represents its handlers as a single multiple handler. To create a multiple
    handler, it takes handlers from the _ERROR_HANDLER_RESOURCE attribute, which
    is represented as one or more handlers. Creates a multiple handler only when
    it's time to interact with the corresponding property, so
    _ERROR_HANDLER_RESOURCE and _MULTIPLE_ERROR_HANDLER_FACTORY attributes are
    constants.
    """

    _ERROR_HANDLER_RESOURCE: Iterable[ErrorHandler] | ErrorHandler
    _MULTIPLE_ERROR_HANDLER_FACTORY: Callable[[Iterable[ErrorHandler]], ErrorHandler] = MultipleHandler

    def _handle_error(self, error: Exception) -> any:
        return self._error_handler(error)

    @cached_property
    def _error_handler(self) -> ErrorHandler:
        """Property representing a proxy of all other handlers used."""

        return (
            self._MULTIPLE_ERROR_HANDLER_FACTORY(self._ERROR_HANDLER_RESOURCE)
            if isinstance(self._ERROR_HANDLER_RESOURCE, Iterable)
            else self._ERROR_HANDLER_RESOURCE
        )


class CustomErrorHandlerMiddleware(ErrorHandlerMiddleware):
    """
    ErrorHandlerMiddleware class with input error handlers. See it for more info.
    """

    def __init__(self, error_handler_resource: Iterable[ErrorHandler] | ErrorHandler):
        self._ERROR_HANDLER_RESOURCE = error_handler_resource

    @cached_property
    def error_handler(self) -> ErrorHandler:
        """
        Public version of ErrorHandlerMiddleware._error_handler property (See it
        for more information).
        """
        
        return self._error_handler