from abc import ABC, abstractmethod
from functools import partial
from typing import Self, Final, Callable, Iterable, ClassVar, Optional

from flask import Blueprint, Flask
from pyhandling import DelegatingProperty
from pyhandling.annotations import decorator

from flask_middlewares.core import IMiddleware, MonolithMiddleware, MultipleMiddleware
from flask_middlewares.errors import MiddlewareRegistrarConfigError
from flask_middlewares.tools import BinarySet


DEFAULT_MIDDLEWARE_CONFIG_FIELD_NAMES: Final[dict[str, str]] = {
    'middlewares': 'MIDDLEWARES',
    'view_names': 'VIEW_NAMES',
    'blueprints': 'BLUEPRINTS',
    'environments': 'ENVIRONMENTS',
    'is_environment_middlewares_higher': 'IS_ENVIRONMENT_HIGHER',
    'use_for_blueprint': 'USE_FOR_BLUEPRINT',
    'is_apply_static': 'IS_APPLY_STATIC',
    'is_apply_root_views': 'IS_APPLY_ROOT_VIEWS'
}


class IMiddlewareRegistrar(ABC):
    @abstractmethod
    def init_app(self, app: Flask) -> None:
        ...


class MiddlewareRegistrar(IMiddlewareRegistrar):
    """
    Class that implements middleware integration in a Flask application.

    Can be created using config variables (See from_config class method).
    """

    __binary_set_attribute_propery_factory = partial(
        DelegatingProperty,
        settable=True,
        setting_converter=BinarySet.create_simulated_by
    )

    view_names = __binary_set_attribute_propery_factory("_view_names")
    blueprints = __binary_set_attribute_propery_factory("_blueprints")

    _proxy_middleware_factory: Callable[[Iterable[IMiddleware | decorator]], MonolithMiddleware] = MultipleMiddleware
    _default_config_field_names: ClassVar[dict[str, str]] = DEFAULT_MIDDLEWARE_CONFIG_FIELD_NAMES

    def __init__(
        self,
        middlewares: Iterable[IMiddleware | decorator],
        *,
        view_names: Iterable[str] = BinarySet(),
        blueprints: Iterable[Blueprint | str] = BinarySet(),
        is_apply_static: bool = False,
        is_apply_root_views: bool = True
    ):
        self._proxy_middleware = self._proxy_middleware_factory(middlewares)

        self.view_names = view_names
        self.blueprints = blueprints

        self.is_apply_static = is_apply_static
        self.is_apply_root_views = is_apply_root_views

    @property
    def middlewares(self) -> tuple[IMiddleware]:
        return self._proxy_middleware.middlewares

    def init_app(self, app: Flask) -> None:
        for view_name, view_function in tuple(app.view_functions.items())[::-1]:
            if self._is_support_view_name_for_registration(view_name):
                app.view_functions[view_name] = self._proxy_middleware.decorate(view_function)

    @classmethod
    def from_config(
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
        config data. Takes the name of standard config of names of this class
        (see DEFAULT_MIDDLEWARE_CONFIG_FIELD_NAMES or
        \"the name of this class\".default_config_field_names) and the config
        variables from the input config_field_names argument.

        Meaning of config variables (Variable names are given by their key in
        config_field_names argument and wrapped in {} brackets):

        {middlewares} - main middlewares with which the registrar will be
        initialized.

        {view_names} - view names with which the registrar will be initialized.

        {blueprints} - blueprints with which the registrar will be initialized.

        {environments} - Dictionary in the format
        [environment_name: str, config: dict] in the config where variables will
        be searched.

        {is_environment_middlewares_higher} - Flag defining the position of ALL
        middlewares from the environment. DEFAULT False.

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

        if environment is not None:
            config = config[config_field_names['environments']].get(environment)

            if config is None:
                raise MiddlewareRegistrarConfigError(f"Environment \"{environment}\" missing")
     
        middlewares = config.get(config_field_names['middlewares'], tuple())

        if not middlewares:
            raise MiddlewareRegistrarConfigError(
                "{config_name} doesn't have any available middlewares".format(
                    config_name=(
                        'The config' if environment is None
                        else f'Environment \"{environment}\"'
                    )
                )
            )

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


class MultipleMiddlewareRegistrar(IMiddlewareRegistrar):
    """
    MiddlewareRegistrar proxy class.

    Used to call multiple registrars to one application.
    """

    def __init__(self, registrars: Iterable[MiddlewareRegistrar]):
        self.registrars = tuple(registrars)

    def init_app(self, app: Flask) -> None:
        for registrar in self.registrars:
            registrar.init_app(app)

    @classmethod
    def from_config(
        cls,
        config: dict,
        *args,
        config_field_names: dict[str, str] = DEFAULT_MIDDLEWARE_CONFIG_FIELD_NAMES,
        registrar_factory: Callable[[dict], IMiddlewareRegistrar] = MiddlewareRegistrar.from_config,
        environments_only: bool = False,
        **kwargs
    ) -> Self:
        """
        Method for creating middleware registrar using config.

        Creates registrars by environment, optionally including the root.

        In keyword arguments, it accepts arguments delegating to Flask's
        registry factory method (Default is
        MiddlewareRegistrar.from_config. See it for default usage).

        Despite delegation, it has several other keyword arguments that control
        the delegation process:

        registrar_factory - Factory for the registrars. Ignore if you don't want
        to initialize the proxy with some other registrars.

        environments_only - Defines the initialization of the registrar
        using general purpose config variables. DEFAULT False. Enable it if you
        want to initialize registrars only from the environments.
        """

        environments = list(config.get(
            config_field_names['environments'],
            dict()
        ).keys())

        if not environments_only:
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