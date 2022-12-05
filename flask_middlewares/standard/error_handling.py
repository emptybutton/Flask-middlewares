from abc import ABC, abstractmethod


class IErrorHandler(ABC):
    def __call__(self, error: Exception) -> any:
        pass
