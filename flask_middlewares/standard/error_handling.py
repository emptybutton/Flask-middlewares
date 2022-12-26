from abc import ABC, abstractmethod
from typing import NewType, Callable, Iterable
from functools import cached_property

from flask import jsonify

from flask_middlewares import Middleware
from flask_middlewares.tools import create_json_response_with


class IErrorHandler(ABC):
    """Callable interface for error handling."""

    def __call__(self, error: Exception) -> any:
        pass


class ProxyErrorHandler(IErrorHandler):
    """
    Error handler proxy class for representing multiple handlers as a single
    interface.

    Has the is_return_delegated flag attribute to enable or disable returning
    the result of one of the handlers.

    When one handler returns anything other than None, it returns that value,
    breaking the loop for other handlers.
    """

    def __init__(
        self,
        error_handlers: Iterable[IErrorHandler] | IErrorHandler,
        *,
        is_return_delegated: bool = True
    ):
        self.is_return_delegated = is_return_delegated
        self.error_handlers = (
            tuple(error_handlers)
            if isinstance(error_handlers, Iterable)
            else (error_handlers, )
        )

    def __call__(self, error: Exception) -> any:
        for error_handler in self.error_handlers:
            result = error_handler(error)

            if self.is_return_delegated and result is not None:
                return result

    @classmethod
    def create_factory_decorator(cls, *args, **kwargs) -> Callable[[Callable], Self]:
        """
        Factory creation method with interface for one handler.

        Passes additional parameters to the created object from the args and
        kwargs of this method.
        """

        def factory_decorator(func: Callable) -> Self:
            """
            Factory created by ProxyErrorHandler.create_factory_decorator method.
            Returns ProxyErrorHandler or its descendant with one input handler.
            """

            return cls((func, ), *args, **kwargs)

        return factory_decorator


class ErrorHandler(IErrorHandler, ABC):
    """
    Class with safe implementation of ErrorHandler interface.
    Handles any specific error and ignores others.
    """

    def __call__(self, error: Exception) -> any:
        if self.is_error_correct_to_handle(error):
            return self._handle_error(error)

    @abstractmethod
    def is_error_correct_to_handle(self, error: Exception) -> bool:
        """Method for determining the reaction to an error."""

    @abstractmethod
    def _handle_error(self, error: Exception) -> any:
        """Method that implements direct handling of a specific error."""


class ErrorHandlerAllower(ErrorHandler):
    """
    ErrorHandler class that enables or disables the work of its handler by
    handling_determinant.

    During initialization, it can take a collection of error handlers, then they
    are converted into a proxy, whose factory passed to the input keyword
    initialization argument.
    """

    def __init__(
        self,
        error_handler_resource: Iterable[IErrorHandler] | IErrorHandler,
        handling_determinant: Callable[[Exception], bool],
        *,
        proxy_error_handler_factory: Callable[[Iterable[IErrorHandler] | IErrorHandler], IErrorHandler] = ProxyErrorHandler
    ):
        self.handling_determinant = handling_determinant
        self.error_handler = (
            proxy_error_handler_factory(error_handler_resource)
            if isinstance(error_handler_resource, Iterable)
            else error_handler_resource
        )

    def is_error_correct_to_handle(self, error: Exception) -> bool:
        return self.handling_determinant(error)

    def _handle_error(self, error: Exception) -> any:
        return self.error_handler(error)


class TypeErrorHandler(ErrorHandler, ABC):
    """
    ErrorHandler class that implements getting the processing flag by error type.

    Has the _is_error_correctness_under_supertype flag attribute that specifies
    whether the error type should match the all error support types.
    """
ErrorHandler = NewType('ErrorHandler', Callable[[Exception], any])

    _correct_error_types_to_handle: Iterable[Exception]
    _is_error_correctness_under_supertype: bool = False

    def is_error_correct_to_handle(self, error: Exception) -> bool:
        return (all if self._is_error_correctness_under_supertype else any)(
            isinstance(error, correct_error_type)
            for correct_error_type in self._correct_error_types_to_handle
        )


class JSONResponseFormatter(ABC):
    """Class that handles objects with a JSON Response as a result."""

    def __init__(
        self,
        *,
        response_factory: Callable[[dict, int], any] = create_json_response_with,
        status_code_resource: Callable[[Exception], int] | int = 200
    ):
        self.response_factory = response_factory
        self.status_code_parser = (
            self.status_code_resource(error)
            if isinstance(status_code_resource, Callable)
            else status_code_resource
        )

    def _handle_error(self, error: Exception) -> any:
        return self.response_factory(
            self._get_response_body_from(error),
            self.status_code_parser(error)
        )

    @abstractmethod
    def _get_response_body_from(self, error: Exception) -> dict | Iterable:
        """Method for getting serialazable body for JSON response by input error."""


class JSONResponseTemplatedErrorFormatter(JSONResponseFormatter):
    """Implementation class of JSONResponseErrorFormatter."""

    def __init__(
        self,
        *,
        response_factory: Callable[[dict, int], any] = create_json_response_with,
        status_code_resource: Callable[[Exception], int] | int = 200,
        is_format_message: bool = True,
        is_format_type: bool = True
    ):
        super().__init__(response_factory=response_factory, status_code_resource=status_code_resource)
        self.is_format_message = is_format_message
        self.is_format_type = is_format_type

    def _get_response_body_from(self, error: Exception) -> dict:
        """Method for getting a message on an error."""

        response_body = dict()

        if self.is_format_message:
            response_body['message'] = self._get_error_message_from(error)

        if self.is_format_type:
            response_body['error-type'] = self._get_error_type_name_from(error)

        return response_body

    def _get_error_message_from(self, error: Exception) -> str:
        """Method for getting the error message by the input error."""

        return str(error)

    def _get_error_type_name_from(self, error: Exception) -> str:
        """
        Method for getting the error type. Doesn't have to be its strict Python
        type.
        """

        return type(error).__name__


class ErrorMiddleware(Middleware, ABC):
    """Middleware class that handles errors that occurred in routers."""

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        try:
            return route(*args, **kwargs)
        except Exception as error:
            return self._handle_error(error)

    @abstractmethod
    def _handle_error(self, error: Exception) -> any:
        """Method that implements response to an error that has occurred."""


class HandlerErrorMiddleware(ErrorMiddleware, ABC):
    """
    ErrorMiddleware delegating error handling to error handlers.

    Represents its handlers as a single proxy handler. To create a proxy, it
    takes handlers from the _ERROR_HANDLER_RESOURCE attribute, which is
    represented as one or more handlers. Creates a proxy handler only when it's
    time to interact with the corresponding property, so _ERROR_HANDLER_RESOURCE
    and _PROXY_ERROR_HANDLER_FACTORY attributes are constants.
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


class CustomHandlerErrorMiddleware(HandlerErrorMiddleware):
    """HandlerErrorMiddleware class with input error handlers."""

    def __init__(self, error_handler_resource: Iterable[ErrorHandler] | ErrorHandler):
        self._ERROR_HANDLER_RESOURCE = error_handler_resource

    @cached_property
    def error_handler(self) -> ErrorHandler:
        """
        Public version of HandlerErrorMiddleware._error_handler property (See it
        for more information).
        """
        
        return self._error_handler