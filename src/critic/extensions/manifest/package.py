from abc import ABC, abstractmethod
from typing import ClassVar, Dict


class Package(ABC):
    package_types: Dict[str, type] = {}
    package_type: ClassVar[str]

    def __init_subclass__(cls, *, package_type: str):
        assert package_type not in Package.package_types
        Package.package_types[package_type] = cls
        cls.package_type = package_type

    @abstractmethod
    def has_entrypoint(self, name: str) -> bool:
        ...
