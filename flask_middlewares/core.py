from abc import ABC, abstractmethod
from typing import Callable, Iterable, Optional
from functools import wraps, partial, reduce

from pyhandling import DelegatingProperty, post_partial, then, on_condition, return_
from pyhandling.annotations import decorator


class IMiddleware(ABC):
    """Middleware interface that dynamically decorates an endpoint function."""

    @abstractmethod
    def decorate(self, route: Callable) -> Callable:
        """
        Method for getting a proxy that delegates the delegation to the
        middleware from which this method was called.
        """

    @abstractmethod
    def call_route(self, route: Callable, *args, **kwargs) -> any:
        """
        Method of delegating the call of an input function with input arguments
        with the execution of tasks.
        """


class MonolithMiddleware(IMiddleware, ABC):
    """
    The abstract base class of middleware (See IMiddleware for more information).

    Implements decorating by creating a proxy function that calls the middleware
    object on the initially decorated function.
    """

    def decorate(self, route: Callable) -> Callable:
        @wraps(route)
        def calling_proxy(*args, **kwargs) -> any:
            return self.call_route(route, *args, **kwargs)

        return calling_proxy


class MultipleMiddleware(MonolithMiddleware):
    """
    Middleware class delegating delegation to other middlewares.

    The resulting call to the router will go from the last middleware to the
    first one, which provides the effect of middleware nesting, where subsequent
    ones are nested in previous ones.
    """

    middlewares = DelegatingProperty("_middlewares")

    def __init__(self, middleware_resources: Iterable[IMiddleware | decorator]):
        self._middlewares = post_partial(map |then>> tuple, middleware_resources)(
            on_condition(
                post_partial(isinstance, IMiddleware),
                return_,
                else_=DecoratorMiddleware
            ),
        )

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        call_layer = route

        for middleware in tuple(self.middlewares)[::-1]:
            call_layer = partial(middleware.call_route, call_layer)

        return call_layer(*args, **kwargs)


class DecoratorMiddleware(IMiddleware):
    """
    Middleware class which is an adapter of classical decorators for the
    Middleware interface.

    Not optimal for using call_route, since every time the router is called, it
    decorates it and only then calls.
    """

    decorator = DelegatingProperty('_decorator')

    def __init__(self, decorator: Callable[[Callable], Callable]):
        self._decorator = decorator

    def decorate(self, route: Callable) -> Callable:
        return reduce(
            lambda route, decorator: decorator(route),
            (route, *self.decorators)
        )

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        return self.decorate(route)(*args, **kwargs)
