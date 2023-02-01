from abc import ABC, abstractmethod
from functools import cached_property, reduce
from typing import Iterable, Optional, Self, Callable, Final

from beautiful_repr import StylizedMixin, Field, TemplateFormatter
from flask import Response, Config, url_for, redirect, jsonify, abort
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


class Aborter:
    """Class that implements the abort of some status code by input resource."""

    def __init__(
        self,
        status_code_resource_to_abort: int | Callable[[any], int],
        *,
        aborter: Callable[[int], any] = abort
    ):
        self.aborter = aborter
        self.aborting_status_code_parser = (
            status_code_resource_to_abort
            if isinstance(status_code_resource_to_abort, Callable)
            else lambda _: status_code_resource_to_abort
        )

    def __call__(self, resource: any) -> any:
        return self.aborter(self.aborting_status_code_parser(resource))


class MultiRange:
    """
    Class containing ranges to provide them as one object.

    Delegates iteration and containing to its ranges.
    You can also create a new Multirange based on an old one with ranges, range
    or another Multirange using the \"|\" operator (or get_with method) on the
    desired resource.
    """

    def __init__(self, range_resource: Iterable[range] | range):
        self._ranges = (
            (range_resource, )
            if isinstance(range_resource, range)
            else tuple(range_resource)
        )

    @property
    def ranges(self) -> tuple[range]:
        return self._ranges

    def get_with(self, range_resource: Self | Iterable[range] | range) -> Self:
        """Method that implements getting a new Multirange with additional ranges."""

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


class StatusCodeResponseFactory:
    """
    Factory class for response with some status code.
    
    Determines the status code from the input response_status_code_resource
    argument, which can be either the status code itself or its parser by
    response.
    """

    def __init__(
        self,
        response_status_code_resource: Callable[[any], int] | int,
        *,
        response_factory: Callable[[any], any] = Response
    ):
        self.response_factory = response_factory
        self.response_status_code_parser = (
            response_status_code_resource
            if isinstance(response_status_code_resource, Callable)
            else lambda _: response_status_code_resource
        )

    def __call__(self, payload: dict) -> Response:
        response = self.response_factory(payload)
        response.status_code = self.response_status_code_parser(payload)

        return response


class BaseExceptionDictTemplater:
    """Formatter class that formatting an error in dict."""

    def __init__(self, *, is_format_message: bool = True, is_format_type: bool = True):
        self.is_format_message = is_format_message
        self.is_format_type = is_format_type

    def __call__(self, error: Exception) -> dict:
        response_body = dict()

        if self.is_format_message:
            response_body['message'] = str(error)

        if self.is_format_type:
            response_body['error-type'] = type(error).__name__

        return response_body



