from abc import ABC, abstractmethod
from typing import Callable, Optional, Iterable, Self

from functools import wraps, partial

from flask import Flask, Blueprint

from flask_middlewares.errors import MiddlewareRegistrarConfigError
from flask_middlewares.tools import BinarySet


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
        def calling_proxy(*args, **kwargs) -> any:
            return self.call_route(route, *args, **kwargs)

        return calling_proxy


class ProxyMiddleware(Middleware):
    def __init__(self, middlewares: Iterable[Middleware]):
        self.middlewares = list(middlewares)

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        call_layer = route

        for middleware in self.middlewares[::-1]:
            call_layer = partial(middleware.call_route, call_layer)

        return call_layer(*args, **kwargs)


class IMiddlewareAppRegistrar(ABC):
    @abstractmethod
    def init_app(
        self,
        app: Flask,
        *,
        for_view_names: Iterable[BinarySet | str] = BinarySet(),
        for_blueprints: Iterable[BinarySet | str | Blueprint] = BinarySet()
    ) -> None:
        pass


class ProxyMiddlewareAppRegistrar(IMiddlewareAppRegistrar):
    def __init__(self, registrars: Iterable[IMiddlewareAppRegistrar]):
        self.registrars = tuple(registrars)

    def init_app(
        self,
        app: Flask,
        *,
        for_view_names: Iterable[BinarySet | str] = BinarySet(),
        for_blueprints: Iterable[BinarySet | str | Blueprint] = BinarySet()
    ) -> None:
        for registrar in self.registrars:
            registrar.init_app(app, for_view_names=for_view_names, for_blueprints=for_blueprints)


class MiddlewareAppRegistrar(IMiddlewareAppRegistrar):
    _proxy_middleware_factory: Callable[[Iterable[Middleware]], Middleware] = ProxyMiddleware
    _config_field_names: dict[str, str] = {
        'middlewares': 'MIDDLEWARES',
        'global_middlewares': 'GLOBAL_MIDDLEWARES',
        'environments': 'MIDDLEWARE_ENVIRONMENTS',
        'default_view_names': 'MIDDLEWARE_VIEW_NAMES',
        'default_blueprints': 'MIDDLEWARE_BLUEPRINTS',
        'is_using_global': 'USE_GLOBAL_MIDDLEWARES',
        'use_for_blueprint': 'USE_FOR_BLUEPRINT',
        'is_global_middlewares_higher': 'IS_GLOBAL_MIDDLEWARES_HIGHER',
        'is_environment_middlewares_higher': 'IS_ENVIRONMENT_MIDDLEWARES_HIGHER'
    }

    def __init__(
        self,
        middlewares: Iterable[Middleware],
        *,
        default_view_names: Optional[Iterable[str] | BinarySet] = None,
        default_blueprints: Optional[Iterable[str | Blueprint] | BinarySet] = None
    ):
        self.middleware = self._proxy_middleware_factory(middlewares)

        self.default_view_name_set = default_view_names
        self.default_blueprint_set = default_blueprints

    @property
    def default_view_name_set(self) -> BinarySet:
        return self._default_view_name_set

    @default_view_name_set.setter
    def default_view_name_set(self, default_view_name_set: Iterable[str]) -> None:
        self._default_view_name_set = self.__get_binary_set_from_raw_data(default_view_name_set)

    @property
    def default_blueprint_set(self) -> BinarySet:
        return self._default_blueprint_set

    @default_blueprint_set.setter
    def default_blueprint_set(self, default_blueprint_set: Iterable[str | Blueprint]) -> None:
        self._default_blueprint_set = self.__get_binary_set_from_raw_data(default_blueprint_set)

    def init_app(
        self,
        app: Flask,
        *,
        for_view_names: Iterable[BinarySet | str] = BinarySet(),
        for_blueprints: Iterable[BinarySet | str | Blueprint] = BinarySet(),
    ) -> None:
        view_name_set = self.default_view_name_set & self.__get_binary_set_from_raw_data(for_view_names)
        blueprint_set = self.default_blueprint_set & self.__get_binary_set_from_raw_data(for_blueprints)

        blueprint_name_set = BinarySet(
            self.__optional_get_blueprint_names_from(blueprint_set.included)
            self.__optional_get_blueprint_names_from(blueprint_set.non_included)
        )

        for view_name, view_function in app.view_functions.items():
            if view_name in view_name_set and any(
                view_blueprint_name in blueprint_name_set
                for view_blueprint_name in view_name.split('.')[:-1]
            ):
                app.view_functions[view_name] = self.middleware.decorate(view_function)

    @classmethod
    def create_from_config(
        cls,
        config: dict,
        *args,
        environment: Optional[str] = None,
        default_view_names: Optional[Iterable[str] | BinarySet] = None,
        default_blueprints: Optional[Iterable[str | Blueprint] | BinarySet] = None,
        is_using_global: Optional[bool] = None,
        use_for_blueprint: Optional[bool | str | Blueprint] = None,
        is_global_middlewares_higher: Optional[bool] = None,
        is_environment_middlewares_higher: Optional[bool] = None,
        **kwargs
    ) -> Self:
        global_middlewares = cls.__get_global_middlewares_from(config)

        if environment is not None:
            global_middlewares = cls.__get_global_middlewares_from(config)
            config = config[cls._config_field_names['environments']].get(environment)

            if config is None:
                raise MiddlewareRegistrarConfigError(f"Environment \"{environment}\" missing")

            environment_global_middlewares = cls.__get_global_middlewares_from(config)

            if (
                config.get(cls._config_field_names['is_environment_middlewares_higher'], False)
                if is_environment_middlewares_higher is None
                else is_environment_middlewares_higher
            ):
                global_middlewares = environment_global_middlewares + global_middlewares
            else:
                global_middlewares += environment_global_middlewares
     
        middlewares = config.get(cls._config_field_names['middlewares'])

        if middlewares is None and not global_middlewares:
            raise MiddlewareRegistrarConfigError(
                "{config_name} doesn't have any available middlewares".format(
                    config_name=(
                        'The config' if environment is None
                        else f'Environment \"{environment}\"'
                    )
                )
            )

        if (
            config.get(cls._config_field_names['is_using_global'], True)
            if is_using_global is None
            else is_using_global
        ):
            middleware_packs = [global_middlewares, middlewares]

            if not (
                config.get(cls._config_field_names['is_global_middlewares_higher'], True)
                if is_global_middlewares_higher is None
                else is_global_middlewares_higher
            ):
                middleware_packs.reverse()

            middlewares = (*middleware_packs[0], *middleware_packs[1])

        if default_view_names is None:
            default_view_names = config.get(cls._config_field_names['default_view_names'])

        if default_blueprints is None:
            default_blueprints = config.get(cls._config_field_names['default_blueprints'])

        use_for_blueprint = (
            config.get(cls._config_field_names['use_for_blueprint'], False)
            if use_for_blueprint is None
            else use_for_blueprint
        )

        if use_for_blueprint:
            if isinstance(use_for_blueprint, bool) and use_for_blueprint:
                if environment is not None:
                    raise MiddlewareRegistrarConfigError(
                        "There is no implicit reference to the blueprint"
                    )

                use_for_blueprint = environment

            if default_blueprints is None:
                default_blueprints = (use_for_blueprint, )

            elif isinstance(default_blueprints, BinarySet):
                default_blueprints.included.add(use_for_blueprint)

            elif isinstance(default_blueprints, Iterable):
                default_blueprints = (*default_blueprints, use_for_blueprint)

        return cls(
            middlewares,
            *args,
            default_view_names=default_view_names,
            default_blueprints=default_blueprints,
            **kwargs,
        )

    @staticmethod
    def __get_binary_set_from_raw_data(raw_data: Iterable) -> BinarySet:
        return raw_data if isinstance(raw_data, BinarySet) else BinarySet(raw_data)

    @staticmethod
    def __optional_get_blueprint_names_from(blueprints: Iterable[str | Blueprint] | None) -> tuple[str] | None:
        return tuple(
            blueprint if isinstance(blueprint, str) else blueprint.name
            for blueprint in blueprints
        ) if blueprints is not None else blueprints

    @classmethod
    def __get_global_middlewares_from(cls, config: dict[str, Iterable[Middleware]]) -> tuple[Middleware]:
        return tuple(config.get(cls._config_field_names['global_middlewares'], tuple()))


class MiddlewareKeeper(ABC):
    _middleware_attribute_names: Iterable[str] = ('_internal_middlewares', )
    _proxy_middleware_factory: Callable[[Iterable[Middleware]], ProxyMiddleware] = ProxyMiddleware

    _proxy_middleware: Optional[ProxyMiddleware]

    def __init__(self):
        self._update_middlewares()

    @property
    def _middlewares(self) -> Middleware:
        return tuple(self._proxy_middleware.middlewares)

    def _update_middlewares(self) -> None:
        self._proxy_middleware = self._proxy_middleware_factory(tuple(self.__parse_middlewares()))

    def __parse_middlewares(self) -> list[Middleware]:
        middlewares = list()

        for attribute_name in self._middleware_attribute_names:
            if not hasattr(self, attribute_name):
                continue

            attribute_value = getattr(self, attribute_name)

            if isinstance(attribute_value, Iterable):
                middlewares.extend(attribute_value)
            else:
                middlewares.append(attribute_value)

        return middlewares