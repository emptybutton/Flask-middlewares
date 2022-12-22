from typing import Iterable, Optional, Self, Callable

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

    In the absence of any values, it considers that everything is present in it.
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

    def __get_changed_by(self, manupulation_methdod: Callable[[set, set], set], other: Self) -> Self:
        included = manupulation_methdod(
            (self.included if self.included is not None else set()),
            (other.included if other.included is not None else set())
        )

        non_included = manupulation_methdod(
            (self.non_included if self.non_included is not None else set()),
            (other.non_included if other.non_included is not None else set())
        )

        return self.__class__(
            included if self.included is not None or other.included is not None else None,
            non_included if self.non_included is not None or other.non_included is not None else None
        )


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


def parse_config_from(
    file_name: str,
    config_parse_method: Callable[[Config, str], None]=Config.from_object
) -> Config:
    config = Config(str())
    config_parse_method(config, file_name)

    return config


def redirect_by(url_resource: str) -> Response:
    try:
        url_resource = url_for(url_resource)
    except BuildError:
        url_resource = url_resource

    return redirect(url_resource)


def create_json_response_with(payload: dict, status_code: int = 200) -> Response:
    response = jsonify(payload)
    response.status_code = self._get_status_code_from(error)

    return response