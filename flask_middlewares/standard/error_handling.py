from abc import ABC, abstractmethod
from typing import Iterable, Self, Callable
from functools import cached_property

from flask import jsonify

from flask_middlewares import Middleware


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


class ErrorHandlerAllower(ProxyErrorHandler):
    """
    ProxyErrorHandler class that disables its middlewares under certain 
    conditions.

    Delegates the definition of middlewares to determinant.
    """

    def __init__(
        self,
        error_handlers: Iterable[IErrorHandler] | IErrorHandler,
        determinant: Callable[[Exception], bool],
        *,
        is_return_delegated: bool = True
    ):
        super().__init__(error_handlers, is_return_delegated=is_return_delegated)
        self.determinant = determinant

    def __call__(self, error: Exception) -> any:
        if self.determinant(error):
            return super().__call__(error)


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


class JSONResponseErrorFormatter(ErrorHandler, ABC):
    """ErrorHandler class that handles errors with a JSON Response as a result."""

    def _handle_error(self, error: Exception) -> any:
        response = jsonify(self._get_response_body_from(error))
        response.status_code = self._get_status_code_from(error)

        return response

    @abstractmethod
    def _get_response_body_from(self, error: Exception) -> dict | Iterable:
        """Method for getting serialazable body for JSON response by input error."""

    @abstractmethod
    def _get_status_code_from(self, error: Exception) -> int:
        """Method for getting status code for response by the input error."""


class JSONResponseTemplatedErrorFormatter(JSONResponseErrorFormatter, ABC):
    """Implementation class of JSONResponseErrorFormatter."""

    _is_format_message: bool = True
    _is_format_type: bool = True

    def _get_response_body_from(self, error: Exception) -> dict:
        """Method for getting a message on an error."""

        response_body = dict()

        if self._is_format_message:
            response_body['message'] = self._get_error_message_from(error)

        if self._is_format_type:
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


class TypeErrorHandler(ErrorHandler, ABC):
    """
    ErrorHandler class that implements getting the processing flag by error type.

    Has the _is_error_correctness_under_supertype flag attribute that specifies
    whether the error type should match the all error support types.
    """

    _correct_error_types_to_handle: Iterable[Exception]
    _is_error_correctness_under_supertype: bool = False

    def is_error_correct_to_handle(self, error: Exception) -> bool:
        return (all if self._is_error_correctness_under_supertype else any)(
            isinstance(error, correct_error_type)
            for correct_error_type in self._correct_error_types_to_handle
        )


class CustomJSONResponseErrorFormatter(JSONResponseTemplatedErrorFormatter, TypeErrorHandler):
    """
    Class that handles all errors that have arisen in the form of a JSON
    response.
    """

    def __init__(
        self,
        error_types: Iterable[type],
        status_code_resource: int | Callable[[Exception], int],
        *,
        is_format_message: bool = True,
        is_format_type: bool = True,
        is_error_correctness_under_supertype: bool = False
    ):
        self.error_types = error_types
        self.status_code_resource = status_code_resource
        self.is_format_message = is_format_message
        self.is_format_type = is_format_type
        self.is_error_correctness_under_supertype = is_error_correctness_under_supertype

    @property
    def error_types(self) -> Iterable[Exception]:
        return self._correct_error_types_to_handle

    @error_types.setter
    def error_types(self, error_types: Iterable[Exception]) -> None:
        self._correct_error_types_to_handle = error_types

    @property
    def is_format_message(self) -> bool:
        return self._is_format_message

    @is_format_message.setter
    def is_format_message(self, is_format_message: bool) -> None:
        self._is_format_message = is_format_message

    @property
    def is_format_type(self) -> bool:
        return self._is_format_type

    @is_format_type.setter
    def is_format_type(self, is_format_type: bool) -> None:
        self._is_format_type = is_format_type

    @property
    def is_error_correctness_under_supertype(self) -> bool:
        return self._is_error_correctness_under_supertype

    @is_error_correctness_under_supertype.setter
    def is_error_correctness_under_supertype(self, is_error_correctness_under_supertype: bool) -> None:
        self._is_error_correctness_under_supertype = is_error_correctness_under_supertype

    def _get_status_code_from(self, error: Exception) -> int:
        return (
            self.status_code_resource(error)
            if isinstance(self.status_code_resource, Callable)
            else self.status_code_resource
        )


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

    _ERROR_HANDLER_RESOURCE: Iterable[IErrorHandler] | IErrorHandler
    _PROXY_ERROR_HANDLER_FACTORY: Callable[[Iterable[IErrorHandler]], IErrorHandler] = ProxyErrorHandler

    def _handle_error(self, error: Exception) -> any:
        return self._error_handler(error)

    @cached_property
    def _error_handler(self) -> IErrorHandler:
        """Property representing a proxy of all other handlers used."""

        return (
            self._PROXY_ERROR_HANDLER_FACTORY(self._ERROR_HANDLER_RESOURCE)
            if isinstance(self._ERROR_HANDLER_RESOURCE, Iterable)
            else self._ERROR_HANDLER_RESOURCE
        )


class CustomHandlerErrorMiddleware(HandlerErrorMiddleware):
    """HandlerErrorMiddleware class with input error handlers."""

    def __init__(self, error_handler_resource: Iterable[IErrorHandler] | IErrorHandler):
        self._ERROR_HANDLER_RESOURCE = error_handler_resource

    @cached_property
    def error_handler(self) -> IErrorHandler:
        """
        Public version of HandlerErrorMiddleware._error_handler property (See it
        for more information).
        """
        
        return self._error_handler