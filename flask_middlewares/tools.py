from abc import ABC, abstractmethod
from functools import cached_property, reduce
from typing import Iterable, Optional, Self, Callable, Final

from beautiful_repr import StylizedMixin, Field, TemplateFormatter
from flask import Response, Config, url_for, redirect
from werkzeug.routing import BuildError


def get_status_code_from(response: any) -> int:
    """Function to get code status from non-structural data."""

    if isinstance(response, Response):
        return response.status_code
    elif (
        isinstance(response, Iterable)
        and len(response) >= 2
        and isinstance(response[1], int | float)
        and int(response[1]) == response[1]
    ):
        return response[1]
    else:
        return 200


class BinarySet(StylizedMixin):
    """
    Like set Class that explicitly stores entities that are not stored in it.

    Storing an empty collection is considered storing. None is used for no
    storage.

    In the case when the set doesn't store anything, it is considered that
    it stores everything.

    Iterable over the values included in the set.
    """

    _repr_fields = (
        Field('included', formatter=TemplateFormatter('{value}')),
        Field('non_included', formatter=TemplateFormatter('{value}'))
    )

    def __init__(self, included: Optional[Iterable] = None, non_included: Optional[Iterable] = None):
        self.included = included
        self.non_included = non_included

    @property
    def included(self) -> set | None:
        return self._included

    @included.setter
    def included(self, included: Iterable | None) -> None:
        self._included = set(included) if included is not None else included

    @property
    def non_included(self) -> set | None:
        return self._non_included

    @non_included.setter
    def non_included(self, non_included: Iterable | None) -> None:
        self._non_included = set(non_included) if non_included is not None else non_included

    def __bool__(self) -> bool:
        return bool(self.included or self.non_included)

    def __iter__(self) -> iter:
        return iter(self.included if self.included is not None else set())

    def __contains__(self, item: any) -> bool:
        return (
            (self.included is None or item in self.included)
            and (self.non_included is None or item not in self.non_included)
        )

    def __eq__(self, other: Self) -> bool:
        return (
            self.included == other.included
            and self.non_included == other.non_included
        )

    def __ne__(self, other: Self) -> bool:
        return not self == other

    def __sub__(self, other: Self) -> Self:
        return self.__get_changed_by(set.__sub__, other)

    def __and__(self, other: Self) -> Self:
        return self.__get_changed_by(set.__and__, other)

    def __or__(self, other: Self) -> Self:
        return self.__get_changed_by(set.__or__, other)

    def __xor__(self, other: Self) -> Self:
        return self.__get_changed_by(set.__xor__, other)

    @classmethod
    def create_simulated_by(cls, collection: Iterable) -> Self:
        return (
            cls(collection.included, collection.non_included)
            if isinstance(collection, BinarySet)
            else cls(collection)
        )

    def __get_changed_by(self, set_manipulation_methdod: Callable[[set, set], set], other: Self) -> Self:
        included = set_manipulation_methdod(
            (self.included if self.included is not None else set()),
            (other.included if other.included is not None else set())
        )

        non_included = set_manipulation_methdod(
            (self.non_included if self.non_included is not None else set()),
            (other.non_included if other.non_included is not None else set())
        )

        return self.__class__(
            included if self.included is not None or other.included is not None else None,
            non_included if self.non_included is not None or other.non_included is not None else None
        )


class HandlerReducer:
    """Handler class that implements handling as a chain of actions of other handlers."""

    def __init__(
        self,
        handler_resource: Iterable[Callable[[any], any]] | Callable[[any], any],
        *handlers: Callable[[any], any]
    ):
        self.handlers = (
            tuple(handler_resource)
            if isinstance(handler_resource, Iterable)
            else (handler_resource, )
        ) + handlers

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({' -> '.join(map(str, self.handlers))})"

    def __call__(self, resource: any) -> any:
        return reduce(
            lambda resource, handler: handler(resource),
            (resource, *self.handlers)
        )


class HandlingBrancher:
    """Handler class that implements branching by its determinant."""

    def __init__(
        self,
        positive_case_handler: Callable[[any], any],
        handling_determinant: Callable[[any], bool],
        negative_case_handler: Callable[[any], any] = lambda _: None
    ):
        self.positive_case_handler = positive_case_handler
        self.handling_determinant = handling_determinant
        self.negative_case_handler = negative_case_handler

    def __call__(self, resource: any) -> any:
        return (
            self.positive_case_handler
            if self.handling_determinant(resource)
            else self.negative_case_handler
        )(resource)


class TypeDeterminant:
    """
    Class that implements checking whether an object conforms to certain types

    Has the is_correctness_under_supertype flag attribute that specifies whether
    the object type should match the all support types.
    """

    def __init__(
        self,
        correct_type_resource: Iterable[Exception] | Exception,
        *,
        is_correctness_under_supertype: bool = False
    ):
        self.is_correctness_under_supertype = is_correctness_under_supertype
        self.correct_types = (
            correct_type_resource
            if isinstance(correct_type_resource, Iterable)
            else (correct_type_resource, )
        )

    def __call__(self, object_: any) -> bool:
        return (
            len(self.correct_types) == 0
            and (all if self.is_correctness_under_supertype else any)(
                isinstance(object_, correct_type)
                for correct_type in self.correct_types
            )
        )


class MultiRange:
    def __init__(self, range_: Iterable[range] | range):
        self._ranges = (
            (range_, )
            if isinstance(range_, range)
            else tuple(range_)
        )

    @property
    def ranges(self) -> tuple[range]:
        return self._ranges

    def get_with(self, range_resource: Self | Iterable[range] | range) -> Self:
        if isinstance(range_resource, MultiRange):
            range_resource = range_resource.ranges

        if isinstance(range_resource, range):
            range_resource = (range_resource, )

        return self.__class__(self.ranges + tuple(range_resource))

    def __repr__(self) -> str:
        return "MultiRange({})".format(', '.join(map(str, self.ranges)))

    def __iter__(self) -> iter:
        return (
            item
            for range_ in self.ranges
            for item in range_
        )

    def __contains__(self, item: any) -> bool:
        return any(
            item in range_
            for range_ in self.ranges
        )

    def __or__(self, range_resource: Self | Iterable[range] | range) -> Self:
        return self.get_with(range_resource)


class StatusCodeGroup:
    """
    Class for storing the HTTP status codes of responses in the form of a
    structure and declarative access to them.
    """

    INFORMATIONAL: Final[MultiRange] = MultiRange(range(100, 200))
    SUCCESSFUL: Final[MultiRange] = MultiRange(range(200, 300))
    REDIRECTION: Final[MultiRange] = MultiRange(range(300, 400))
    CLIENT_ERROR: Final[MultiRange] = MultiRange(range(400, 500))
    SERVER_ERROR: Final[MultiRange] = MultiRange(range(500, 600))

    GOOD: Final[MultiRange] = MultiRange(range(100, 400))
    ERROR: Final[MultiRange] = MultiRange(range(400, 600))

    ALL: Final[MultiRange] = MultiRange(range(100, 600))


def parse_config_from(
    file_name: str,
    config_parse_method: Callable[[Config, str], None]=Config.from_object
) -> Config:
    """Function for creating a config, delegating the update method to it."""

    config = Config(str())
    config_parse_method(config, file_name)

    return config


def redirect_by(url_resource: str) -> Response:
    """Function to get redirect with possible url from blueprints."""

    try:
        url_resource = url_for(url_resource)
    except BuildError:
        url_resource = url_resource

    return redirect(url_resource)


def create_json_response_with(payload: dict, status_code: int = 200) -> Response:
    """Function to generate flask response with JSON data and status code."""

    response = jsonify(payload)
    response.status_code = self._get_status_code_from(error)

    return response