from abc import ABC, abstractmethod
from pathlib import Path


class ProgressReporter(ABC):
    @abstractmethod
    def start(self, total: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def advance(self, amount: int = 1) -> None:
        raise NotImplementedError

    @abstractmethod
    def log(self, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError
