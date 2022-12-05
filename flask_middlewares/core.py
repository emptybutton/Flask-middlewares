from abc import ABC, abstractmethod
from typing import Callable, Optional, Iterable, Self

from functools import wraps, partial


class IMiddleware(ABC):
    @abstractmethod
    def decorate(self, route: Callable) -> Callable:
        pass

    @abstractmethod
    def call_route(self, route: Callable, *args, **kwargs) -> any:
        pass


class Middleware(IMiddleware, ABC):
    def decorate(self, route: Callable) -> Callable:
        @wraps(route)
        def body(*args, **kwargs) -> any:
            return self.call_route(route, *args, **kwargs)

        return body


class ProxyMiddleware(Middleware):
    def __init__(self, middlewares: Iterable[Middleware]):
        self.middlewares = list(middlewares)

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        call_layer = route

        for middleware in self.middlewares[::-1]:
            call_layer = partial(middleware.call_route, call_layer)

        return call_layer(*args, **kwargs)
        pass
