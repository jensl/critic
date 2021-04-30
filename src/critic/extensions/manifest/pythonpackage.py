from typing import Dict, List

from .package import Package


class PythonPackage(Package, package_type="python"):
    entrypoints: Dict[str, str]
    dependencies: List[str]
    data_globs: List[str]

    def __init__(self) -> None:
        self.entrypoints = {}
        self.dependencies = []
        self.data_globs = []

    def add_entrypoint(self, name: str, target: str) -> None:
        self.entrypoints[name] = target

    def add_dependency(self, dependency: str) -> None:
        self.dependencies.append(dependency)

    def add_data_glob(self, glob: str) -> None:
        self.data_globs.append(glob)

    def has_entrypoint(self, name: str) -> bool:
        return name in self.entrypoints
