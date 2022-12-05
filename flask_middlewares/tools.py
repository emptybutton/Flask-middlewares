from typing import Iterable, Optional, Self, Callable

from beautiful_repr import StylizedMixin, Field, TemplateFormatter
from flask import Response


def get_status_code_from(response: any) -> int:
    if isinstance(response, Response):
        return response.status_code
    elif (
        isinstance(response, Iterable)
        and len(response) >= 2
        and isinstance(response[1], int | float)
        and int(response[1]) == response[1]
        and 400 <= response[1] <= 500
    ):
        return response[1]
    else:
        return 200


class BinarySet(StylizedMixin):
    _repr_fields = (
        Field('including', formatter=TemplateFormatter('{value}')),
        Field('non_including', formatter=TemplateFormatter('{value}'))
    )

    def __init__(self, including: Optional[Iterable] = None, non_including: Optional[Iterable] = None):
        self.including = including
        self.non_including = non_including

    @property
    def including(self) -> set | None:
        return self._including

    @including.setter
    def including(self, including: Iterable | None) -> None:
        self._including = set(including) if including is not None else including

    @property
    def non_including(self) -> set | None:
        return self._non_including

    @non_including.setter
    def non_including(self, non_including: Iterable | None) -> None:
        self._non_including = set(non_including) if non_including is not None else non_including

    def __bool__(self) -> bool:
        return bool(self.including or self.non_including)

    def __contains__(self, item: any) -> bool:
        return (
            (self.including is None or item in self.including)
            and (self.non_including is None or item not in self.non_including)
        )

    def __eq__(self, other: Self) -> bool:
        return (
            self.including == other.including
            and self.non_including == other.non_including
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
        including = manupulation_methdod(
            (self.including if self.including is not None else set()),
            (other.including if other.including is not None else set())
        )

        non_including = manupulation_methdod(
            (self.non_including if self.non_including is not None else set()),
            (other.non_including if other.non_including is not None else set())
        )

        return self.__class__(
            including if self.including is not None and other.including is not None else None,
            non_including if self.non_including is not None and other.non_including is not None else None
        )