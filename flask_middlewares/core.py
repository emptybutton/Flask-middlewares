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


class MiddlewareKeeper(ABC):
    """
    Base middleware storage class.

    Stores middleware as a proxy that it delegates when accessing middleware.
    When updating (and initializing) the proxy parses the middlewares from the
    _middleware_attribute_names attributes.

    Despite the storage of middlewares in the form of a proxy, it has the ability
    to interact with them by delegating interaction to the proxy.

    Not strict on missing middleware attributes, which can be changed by setting
    `_is_strict_to_middleware_attribute_parsing = True`.

    Parses iterable attributes as attribute items.
    """

    _middleware_attribute_names: Iterable[str] = ('_default_middlewares', )
    _is_strict_to_middleware_attribute_parsing: bool = False

    _proxy_middleware_factory: Callable[[Iterable[IMiddleware]], ProxyMiddleware] = ProxyMiddleware

    _proxy_middleware: Optional[ProxyMiddleware]

    def __init__(self):
        self._update_proxy_middleware()

    @property
    def _middlewares(self) -> Iterable[IMiddleware]:
        return self._proxy_middleware.middlewares

    @_middlewares.setter
    def _middlewares(self, middlewares: Iterable[IMiddleware]) -> None:
        self._proxy_middleware.middlewares = middlewares

    def _update_proxy_middleware(self) -> None:
        """Method for creating | updating _proxy_middleware from attributes."""

        self._proxy_middleware = self._proxy_middleware_factory(tuple(self.__get_parsed_middlewares()))

    def __get_parsed_middlewares(self) -> list[IMiddleware]:
        """
        Middleware parsing method from attributes whose name is given in the
        _middleware_attribute_names attribute.
        """

        middlewares = list()

        for attribute_name in self._middleware_attribute_names:
            if (
                not hasattr(self, attribute_name)
                and not self._is_strict_to_middleware_attribute_parsing
            ):
                continue

            attribute_value = getattr(self, attribute_name)

            if isinstance(attribute_value, Iterable):
                middlewares.extend(attribute_value)
            else:
                middlewares.append(attribute_value)

        return middlewares