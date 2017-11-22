from typing import Dict, List

from .package import Package


class PythonPackage(Package, package_type="python"):
    entrypoints: Dict[str, str]
    dependencies: List[str]

    def __init__(self) -> None:
        self.entrypoints = {}
        self.dependencies = []

    def add_entrypoint(self, name: str, target: str) -> None:
        self.entrypoints[name] = target

    def add_dependency(self, dependency: str) -> None:
        self.dependencies.append(dependency)
