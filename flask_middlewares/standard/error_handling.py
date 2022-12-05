from abc import ABC, abstractmethod
from typing import Iterable, Self, Callable


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
