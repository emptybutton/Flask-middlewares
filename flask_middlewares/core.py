from abc import ABC, abstractmethod
from typing import Callable, Optional, Iterable, Self
from functools import wraps, partial

from flask import Flask, Blueprint

from flask_middlewares.errors import MiddlewareRegistrarConfigError
from flask_middlewares.tools import BinarySet


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


class Middleware(IMiddleware, ABC):
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


class ProxyMiddleware(Middleware):
    """Middleware class delegating delegation to other middlewares."""

    def __init__(self, middlewares: Iterable[IMiddleware]):
        self.middlewares = middlewares

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        call_layer = route

        for middleware in self.middlewares[::-1]:
            call_layer = partial(middleware.call_route, call_layer)

        return call_layer(*args, **kwargs)


class IAppMiddlewareRegistrar(ABC):
    """Registrar interface for middleware integration with Flask application."""

    @abstractmethod
    def init_app(
        self,
        app: object,
        *,
        for_view_names: Iterable[str] = BinarySet(),
        for_blueprints: Iterable[str | Blueprint] = BinarySet()
    ) -> None:
        """
        Method for integrating middlewares with input application.

        Accepts additional optional arguments:
        * for_view_names - View function names to be integrated.

        * for_blueprints - Blueprints whose view functions will be integrated.
            Сan contain raw blueprint names.
        """

    @classmethod
    @abstractmethod
    def create_from_config(cls, config: dict, *args, **kwargs) -> Self:
        """
        Method for creating middleware registrar using config.

        In keyword arguments, it accepts arguments that complement | overwriting
        config data.
        """


DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES: dict[str, str] = {
    'middlewares': 'MIDDLEWARES',
    'global_middlewares': 'GLOBAL_MIDDLEWARES',
    'environments': 'MIDDLEWARE_ENVIRONMENTS',
    'default_view_names': 'MIDDLEWARE_VIEW_NAMES',
    'default_blueprints': 'MIDDLEWARE_BLUEPRINTS',
    'is_using_global': 'USE_GLOBAL_MIDDLEWARES',
    'use_for_blueprint': 'USE_FOR_BLUEPRINT',
    'is_global_middlewares_higher': 'IS_GLOBAL_MIDDLEWARES_HIGHER',
    'is_environment_middlewares_higher': 'IS_ENVIRONMENT_MIDDLEWARES_HIGHER',
    'is_apply_static': 'IS_APPLY_STATIC'
}


class FlaskAppMiddlewareRegistrar(IAppMiddlewareRegistrar):
    """
    Class that implements middleware integration in a Flask application.

    Can be created using config variables (See create_from_config class method).
    """

    _proxy_middleware_factory: Callable[[Iterable[IMiddleware]], ProxyMiddleware] = ProxyMiddleware

    def __init__(
        self,
        middlewares: Iterable[IMiddleware],
        *,
        default_view_names: Iterable[str] = BinarySet(),
        default_blueprints: Iterable[str | Blueprint] = BinarySet(),
        is_apply_static: bool = False
    ):
        self.proxy_middleware = self._proxy_middleware_factory(middlewares)

        self.default_view_name_set = default_view_names
        self.default_blueprint_set = default_blueprints

        self.is_apply_static = is_apply_static

    @property
    def middlewares(self) -> Iterable[IMiddleware]:
        return self.proxy_middleware.middlewares

    @middlewares.setter
    def middlewares(self, middlewares: Iterable[IMiddleware]) -> None:
        self.proxy_middleware.middlewares = middlewares

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
        for_view_names: Iterable[str] = BinarySet(),
        for_blueprints: Iterable[str | Blueprint] = BinarySet(),
    ) -> None:
        view_names = self.default_view_name_set | self.__get_binary_set_from_raw_data(for_view_names)
        blueprint_names = self.default_blueprint_set | self.__get_binary_set_from_raw_data(for_blueprints)

        blueprint_names = BinarySet(
            self.__optional_get_blueprint_names_from(blueprint_names.included),
            self.__optional_get_blueprint_names_from(blueprint_names.non_included)
        )

        for view_name, view_function in app.view_functions.items():
            view_blueprint_names = view_name.split('.')[:-1]

            if (
                (view_name != 'static' or self.is_apply_static)
                and view_name in view_names
                and (not view_blueprint_names and not blueprint_names or any(
                    view_blueprint_name in blueprint_names
                    for view_blueprint_name in view_blueprint_names
                ))
            ):
                app.view_functions[view_name] = self.proxy_middleware.decorate(view_function)

    @classmethod
    def create_from_config(
        cls,
        config: dict,
        *args,
        config_field_names: dict[str, str] = DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES,
        environment: Optional[str] = None,
        default_view_names: Optional[Iterable[str] | BinarySet] = None,
        default_blueprints: Optional[Iterable[str | Blueprint] | BinarySet] = None,
        is_using_global: Optional[bool] = None,
        use_for_blueprint: Optional[bool | str | Blueprint] = None,
        is_global_middlewares_higher: Optional[bool] = None,
        is_environment_middlewares_higher: Optional[bool] = None,
        is_apply_static: Optional[bool] = None,
        **kwargs
    ) -> Self:
        """
        Method for creating middleware registrar using config.

        In keyword arguments, it accepts arguments that complement | overwriting
        config data. Takes the name of the config variables from the input
        _config_field_names argument (By default, see DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES).

        Meaning of config variables (Variable names are given by their key in
        _config_field_names argument and wrapped in {} brackets):

        {middlewares} - main middlewares with which the registrar will be
        initialized.

        {default_view_names} - view names with which the registrar will be
        initialized.

        {default_blueprints} - blueprints with which the registrar will be
        initialized.

        {global_middlewares} - Additional middleware globally added to registrars,

        {is_using_global} - Flag indicating the presence of middlewares from
        {global_middlewares}. DEFAULT True.

        {is_global_middlewares_higher} - Flag denoting the locations of
        middlewares from {global_middlewares} DEFAULT True.

        {environments} - Dictionary in the format
        [environment_name: str, config: dict] in the config where variables will
        be searched except for {global_middlewares} which will be taken from the
        original.

        {is_environment_middlewares_higher} - Flag defining the position of ALL
        (including global) middlewares from the environment. DEFAULT False.

        {use_for_blueprint} - When assigned, adds the blueprint from the value
        of the variable to the default_blueprints attribute. Can be set to True
        when in an environment, in which case it takes the name of the
        environment as the blueprint name. It is better to use only in the
        environment but no one limits you.

        {is_apply_static} - Specifies the application to the \"system\" flask
        view getting static resources. DEFAULT False. It's better not to turn it
        on if you don't know what you are doing.
        """

        global_middlewares = cls.__get_global_middlewares_from(config, config_field_names)

        if environment is not None:
            global_middlewares = cls.__get_global_middlewares_from(config, config_field_names)
            config = config[config_field_names['environments']].get(environment)

            if config is None:
                raise MiddlewareRegistrarConfigError(f"Environment \"{environment}\" missing")

            environment_global_middlewares = cls.__get_global_middlewares_from(config, config_field_names)

            if (
                config.get(config_field_names['is_environment_middlewares_higher'], False)
                if is_environment_middlewares_higher is None
                else is_environment_middlewares_higher
            ):
                global_middlewares = environment_global_middlewares + global_middlewares
            else:
                global_middlewares += environment_global_middlewares
     
        middlewares = config.get(config_field_names['middlewares'], tuple())

        if not middlewares and not global_middlewares:
            raise MiddlewareRegistrarConfigError(
                "{config_name} doesn't have any available middlewares".format(
                    config_name=(
                        'The config' if environment is None
                        else f'Environment \"{environment}\"'
                    )
                )
            )

        if (
            config.get(config_field_names['is_using_global'], True)
            if is_using_global is None
            else is_using_global
        ):
            middleware_packs = [global_middlewares, middlewares]

            if not (
                config.get(config_field_names['is_global_middlewares_higher'], True)
                if is_global_middlewares_higher is None
                else is_global_middlewares_higher
            ):
                middleware_packs.reverse()

            middlewares = (*middleware_packs[0], *middleware_packs[1])

        if default_view_names is None:
            default_view_names = config.get(config_field_names['default_view_names'])

        if default_blueprints is None:
            default_blueprints = config.get(config_field_names['default_blueprints'])

        use_for_blueprint = (
            config.get(config_field_names['use_for_blueprint'])
            if use_for_blueprint is None
            else use_for_blueprint
        )

        if use_for_blueprint is not None:
            if isinstance(use_for_blueprint, bool) and use_for_blueprint:
                if environment is None:
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

        if is_apply_static is not None:
            kwargs['is_apply_static'] = is_apply_static

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
    def __get_global_middlewares_from(
        cls,
        config: dict[str, Iterable[IMiddleware]],
        config_field_names: dict[str, str]
    ) -> tuple[IMiddleware]:
        return tuple(config.get(config_field_names['global_middlewares'], tuple()))


class ProxyFlaskAppMiddlewareRegistrar(IAppMiddlewareRegistrar):
    """
    FlaskAppMiddlewareRegistrar proxy class.

    Used to call multiple registrars to one application.
    """

    def __init__(self, registrars: Iterable[FlaskAppMiddlewareRegistrar]):
        self.registrars = tuple(registrars)

    def init_app(
        self,
        app: Flask,
        *,
        for_view_names: Iterable[str] = BinarySet(),
        for_blueprints: Iterable[str | Blueprint] = BinarySet()
    ) -> None:
        for registrar in self.registrars:
            registrar.init_app(app, for_view_names=for_view_names, for_blueprints=for_blueprints)

    @classmethod
    def create_from_config(
        cls,
        config: dict,
        *args,
        config_field_names: dict[str, str] = DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES,
        registrar_factory: Callable[[dict], IAppMiddlewareRegistrar] = AppMiddlewareRegistrar.create_from_config,
        is_root_registrar_creating: bool = True,
        environment: None = None,
        **kwargs
    ) -> Self:
        environment_arguments = set(config.get(
            config_field_names['environments'],
            dict()
        ).keys())

        if is_root_registrar_creating:
            environment_arguments.add(None)

        return cls(
            registrar_factory(
                config,
                *args,
                environment=environment_argument,
                config_field_names=config_field_names,
                **kwargs
            )
            for environment_argument in environment_arguments
        )


class MiddlewareKeeper(ABC):
    """Base middleware storage class."""
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