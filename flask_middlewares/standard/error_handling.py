from abc import ABC, abstractmethod
from typing import Iterable, Self, Callable
from functools import cached_property

from flask_middlewares import Middleware


class IErrorHandler(ABC):
    def __call__(self, error: Exception) -> any:
        pass


class ProxyErrorHandler(IErrorHandler):
    def __init__(self, error_handlers: Iterable[IErrorHandler], *, is_return_delegated: bool = True):
        self.error_handlers = tuple(error_handlers)
        self.is_return_delegated = is_return_delegated

    def __call__(self, error: Exception) -> any:
        for error_handler in self.error_handlers:
            result = error_handler(error)

            if self.is_return_delegated and result is not None:
                return result

    @classmethod
    def create_factory_decorator(cls, *args, **kwargs) -> Callable[[Callable], Self]:
        def factory_decorator(func: Callable) -> Self:
            return cls((func, ), *args, **kwargs)

        return factory_decorator


class ErrorHandler(IErrorHandler, ABC):
    def __call__(self, error: Exception) -> any:
        if self.is_error_correct_to_handle(error):
            return self._handle_error(error)

    @abstractmethod
    def is_error_correct_to_handle(self, error: Exception) -> bool:
        pass

    @abstractmethod
    def _handle_error(self, error: Exception) -> any:
        pass


class ErrorJSONResponseFormatter(ErrorHandler, ABC):
    def _handle_error(self, error: Exception) -> any:
        response = jsonify(self._get_response_body_from(error))
        response.status_code = self._get_status_code_from(error)

        return response

    @abstractmethod
        pass
    def _get_response_body_from(self, error: Exception) -> dict | Iterable:

    @abstractmethod
    def _get_status_code_from(self, error: Exception) -> int:
        pass


class TemplatedErrorJSONResponseFormatter(ErrorJSONResponseFormatter, ABC):
    def __init__(self, is_format_message: bool = True, is_format_type: bool = False):
        self.is_format_message = is_format_message
        self.is_format_type = is_format_type

    def _get_response_body_from(self, error: Exception) -> dict:
        response_body = dict()

        if self.is_format_message:
            response_body['message'] = self._get_error_message_from(error)

        if self.is_format_type:
            response_body['error-type'] = self._get_error_type_name_from(error)

        return response_body

    def _get_error_message_from(self, error: Exception) -> str:
        return str(error)

    def _get_error_type_name_from(self, error: Exception) -> str:
        return type(error).__name__


class TypeErrorHandler(ErrorHandler, ABC):
    _correct_error_types_to_handle: Iterable[Exception]
    _is_error_correctness_under_supertype: bool = False

    def is_error_correct_to_handle(self, error: Exception) -> bool:
        return (all if self._is_error_correctness_under_supertype else any)(
            isinstance(error, correct_error_type)
            for correct_error_type in self._correct_error_types_to_handle
        )


class ErrorMiddleware(Middleware, ABC):
    def call_route(self, route: Callable, *args, **kwargs) -> any:
        try:
            return route(*args, **kwargs)
        except Exception as error:
            return self._handle_error(error)

    @abstractmethod
    def _handle_error(self, error: Exception) -> any:
        pass


class HandlerErrorMiddleware(ErrorMiddleware, ABC):
    _ERROR_HANDLER_RESOURCE: Iterable[IErrorHandler] | IErrorHandler
    _PROXY_ERROR_HANDLER_FACTORY: Callable[[Iterable[IErrorHandler]], IErrorHandler] = ProxyErrorHandler

    def _handle_error(self, error: Exception) -> any:
        return self._error_handler(error)

    @cached_property
    def _error_handler(self) -> IErrorHandler:
        return (
            self._PROXY_ERROR_HANDLER_FACTORY(self._ERROR_HANDLER_RESOURCE)
            if isinstance(self._ERROR_HANDLER_RESOURCE, Iterable)
            else self._ERROR_HANDLER_RESOURCE
        )


class CustomHandlerErrorMiddleware(HandlerErrorMiddleware):
    def __init__(self, error_handler_resource: Iterable[IErrorHandler] | IErrorHandler):
        self._ERROR_HANDLER_RESOURCE = error_handler_resource

    @cached_property
    def error_handler(self) -> IErrorHandler:
        return self._error_handler