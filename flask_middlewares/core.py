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
    """
    Middleware class delegating delegation to other middlewares.

    The resulting call to the router will go from the last middleware to the
    first one, which provides the effect of middleware nesting, where subsequent
    ones are nested in previous ones.
    """

    def __init__(self, middlewares: Iterable[IMiddleware]):
        self.middlewares = middlewares

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        call_layer = route

        for middleware in tuple(self.middlewares)[::-1]:
            call_layer = partial(middleware.call_route, call_layer)

        return call_layer(*args, **kwargs)


class IAppMiddlewareRegistrar(ABC):
    """Registrar interface for middleware integration with some application."""

    @abstractmethod
    def init_app(self, app: object) -> None:
        """Method for integrating middlewares with input application."""

    @classmethod
    @abstractmethod
    def create_from_config(cls, config: dict, *args, **kwargs) -> Self:
        """
        Method for creating middleware registrar using config.

        In keyword arguments, it accepts arguments that complement | overwriting
        config data.
        """


DEFAULT_APP_CONFIG_FIELD_NAMES: dict[str, str] = {
    'middlewares': 'MIDDLEWARES',
    'global_middlewares': 'GLOBAL_MIDDLEWARES',
    'environments': 'MIDDLEWARE_ENVIRONMENTS',
    'is_using_global': 'USE_GLOBAL_MIDDLEWARES',
    'is_global_middlewares_higher': 'IS_GLOBAL_MIDDLEWARES_HIGHER',
    'is_environment_middlewares_higher': 'IS_ENVIRONMENT_MIDDLEWARES_HIGHER'
}

DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES: dict[str, str] = {
    **DEFAULT_APP_CONFIG_FIELD_NAMES,
    'view_names': 'MIDDLEWARE_VIEW_NAMES',
    'blueprints': 'MIDDLEWARE_BLUEPRINTS',
    'use_for_blueprint': 'USE_FOR_BLUEPRINT',
    'is_apply_static': 'IS_APPLY_STATIC',
    'is_apply_root_views': 'IS_APPLY_ROOT_VIEWS'
}


class FlaskAppMiddlewareRegistrar(IAppMiddlewareRegistrar):
    """
    Class that implements middleware integration in a Flask application.

    Can be created using config variables (See create_from_config class method).
    """

    _proxy_middleware_factory: Callable[[Iterable[IMiddleware]], ProxyMiddleware] = ProxyMiddleware
    _default_config_field_names: dict[str, str] = DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES

    def __init__(
        self,
        middlewares: Iterable[IMiddleware],
        *,
        view_names: Iterable[str] = BinarySet(),
        blueprints: Iterable[str | Blueprint] = BinarySet(),
        is_apply_static: bool = False,
        is_apply_root_views: bool = True
    ):
        self.proxy_middleware = self._proxy_middleware_factory(middlewares)

        self.view_names = view_names
        self.blueprints = blueprints

        self.is_apply_static = is_apply_static
        self.is_apply_root_views = is_apply_root_views

    @property
    def middlewares(self) -> Iterable[IMiddleware]:
        return self.proxy_middleware.middlewares

    @middlewares.setter
    def middlewares(self, middlewares: Iterable[IMiddleware]) -> None:
        self.proxy_middleware.middlewares = middlewares

    @property
    def view_names(self) -> BinarySet:
        return self._view_names

    @view_names.setter
    def view_names(self, view_names: Iterable[str]) -> None:
        self._view_names = BinarySet.create_simulated_by(view_names)

    @property
    def blueprints(self) -> BinarySet:
        return self._blueprints

    @blueprints.setter
    def blueprints(self, blueprints: Iterable[str | Blueprint]) -> None:
        self._blueprints = BinarySet.create_simulated_by(blueprints)

    def init_app(self, app: Flask) -> None:
        for view_name, view_function in tuple(app.view_functions.items())[::-1]:
            if self._is_support_view_name_for_registration(view_name):
                app.view_functions[view_name] = self.proxy_middleware.decorate(view_function)

    @classmethod
    @property
    def default_config_field_names(cls) -> dict[str, str]:
        return cls._default_config_field_names

    @classmethod
    def create_from_config(
        cls,
        config: dict,
        *args,
        config_field_names: dict[str, str] = dict(),
        environment: Optional[str] = None,
        view_names: Optional[Iterable[str] | BinarySet] = None,
        blueprints: Optional[Iterable[str | Blueprint] | BinarySet] = None,
        is_using_global: Optional[bool] = None,
        use_for_blueprint: Optional[bool | str | Blueprint] = None,
        is_global_middlewares_higher: Optional[bool] = None,
        is_environment_middlewares_higher: Optional[bool] = None,
        is_apply_root_views: Optional[bool] = None,
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

        {view_names} - view names with which the registrar will be
        initialized.

        {blueprints} - blueprints with which the registrar will be
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
        of the variable to the blueprints attribute and disables
        {is_apply_root_views} if it is not set somehow. Can be set to True when
        in an environment, in which case it takes the name of the environment as
        the blueprint name. It is better to use only in the environment but no
        one limits you.

        {is_apply_static} - Specifies the application to the \"system\" flask
        view getting static resources. DEFAULT False. It's better not to turn it
        on if you don't know what you are doing.

        {is_apply_root_views} - Defines registration for view functions not
        related to blueprints. DEFAULT True.
        """

        config_field_names = cls._default_config_field_names | config_field_names

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

        if view_names is None:
            view_names = config.get(config_field_names['view_names'])

        if blueprints is None:
            blueprints = config.get(config_field_names['blueprints'])

        if is_apply_root_views is None:
            is_apply_root_views = config.get(config_field_names['is_apply_root_views'])

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

            if blueprints is None:
                blueprints = (use_for_blueprint, )

            elif isinstance(blueprints, BinarySet):
                blueprints.included.add(use_for_blueprint)

            elif isinstance(blueprints, Iterable):
                blueprints = (*blueprints, use_for_blueprint)

            if is_apply_root_views is None:
                is_apply_root_views = False


        if is_apply_root_views is not None:
            kwargs['is_apply_root_views'] = is_apply_root_views

        cls.__optionally_copy_config_field_to_another('is_apply_root_views', config, kwargs, config_field_names)

        return cls(
            middlewares,
            *args,
            view_names=view_names,
            blueprints=blueprints,
            **kwargs,
        )

    def _is_support_view_name_for_registration(self, view_name: str) -> bool:
        return (
            (view_name != 'static' or self.is_apply_static)
            and view_name in self.view_names
            and self._is_support_view_name_for_blueprints(view_name)
        )

    def _is_support_view_name_for_blueprints(self, view_name: str) -> bool:
        view_blueprint_names = view_name.split('.')[:-1]

        blueprint_names = BinarySet(
            self.__optional_get_blueprint_names_from(self.blueprints.included),
            self.__optional_get_blueprint_names_from(self.blueprints.non_included)
        )

        return (
            not view_blueprint_names
            and self.is_apply_root_views
            or any(
                view_blueprint_name in blueprint_names
                for view_blueprint_name in view_blueprint_names
            )
        )

    @staticmethod
    def __optional_get_blueprint_names_from(blueprints: Iterable[str | Blueprint] | None) -> tuple[str] | None:
        return tuple(
            blueprint if isinstance(blueprint, str) else blueprint.name
            for blueprint in blueprints
        ) if blueprints is not None else blueprints

    @staticmethod
    def __get_global_middlewares_from(
        config: dict[str, Iterable[IMiddleware]],
        config_field_names: dict[str, str]
    ) -> tuple[IMiddleware]:
        return tuple(config.get(config_field_names['global_middlewares'], tuple()))

    @staticmethod
    def __optionally_copy_config_field_to_another(
        field_name: str,
        config_owner: dict,
        config_recipient: dict,
        config_field_names: dict
    ) -> None:
        field_value = config_recipient.get(field_name)

        if field_value is None:
            config_owner.get(config_field_names[field_name])

        if field_value is not None:
            config_recipient[field_name] = field_value

        return field_value


class ProxyFlaskAppMiddlewareRegistrar(IAppMiddlewareRegistrar):
    """
    FlaskAppMiddlewareRegistrar proxy class.

    Used to call multiple registrars to one application.
    """

    def __init__(self, registrars: Iterable[FlaskAppMiddlewareRegistrar]):
        self.registrars = registrars

    def init_app(self, app: Flask) -> None:
        for registrar in self.registrars:
            registrar.init_app(app)

    @classmethod
    def create_from_config(
        cls,
        config: dict,
        *args,
        config_field_names: dict[str, str] = DEFAULT_FLASK_APP_CONFIG_FIELD_NAMES,
        registrar_factory: Callable[[dict], IAppMiddlewareRegistrar] = FlaskAppMiddlewareRegistrar.create_from_config,
        is_root_registrar_creating: bool = True,
        **kwargs
    ) -> Self:
        """
        Method for creating middleware registrar using config.

        Creates registrars by environment, optionally including the root.

        In keyword arguments, it accepts arguments delegating to Flask's
        registry factory method (Default is
        FlaskAppMiddlewareRegistrar.create_from_config. See it for default usage).

        Despite delegation, it has several other keyword arguments that control
        the delegation process:

        registrar_factory - Factory for the registrars. Ignore if you don't want
        to initialize the proxy with some other registrars.

        is_root_registrar_creating - Defines the initialization of the registrar
        using general purpose config variables. DEFAULT True. Disable it if you
        want to initialize registrars only from the environments. Doesn't change
        the influence of the standard environment on other environments.
        """

        environments = list(config.get(
            config_field_names['environments'],
            dict()
        ).keys())

        if is_root_registrar_creating:
            environments.append(None)

        return cls(
            registrar_factory(
                config,
                *args,
                config_field_names=config_field_names,
                environment=environment,
                **kwargs
            )
            for environment in environments
        )


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