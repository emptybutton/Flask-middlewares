from abc import ABC, abstractmethod
from functools import cached_property, reduce
from typing import Iterable, Optional, Self, Callable, Final

from beautiful_repr import StylizedMixin, Field, TemplateFormatter
from flask import Response, Config, url_for, redirect, jsonify, abort
from werkzeug.routing import BuildError




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


