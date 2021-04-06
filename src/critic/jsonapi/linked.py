from __future__ import annotations

from typing import Set, Any, Type, cast

from critic import api
from .parameters import Parameters
from .resourceclass import APIObject


class Linked(object):
    def __init__(self, parameters: Parameters):
        self.parameters = parameters
        self.critic = parameters.critic
        self.linked_per_type = {
            resource_type: parameters.getLinked(resource_type)
            for resource_type in parameters.include
        }

    def __getitem__(self, resource_type: str) -> Set[Any]:
        return self.linked_per_type[resource_type]

    def __setitem__(self, resource_type: str, value: Any) -> None:
        self.linked_per_type[resource_type] = value

    def isEmpty(self) -> bool:
        return not any(self.linked_per_type.values())

    def add(
        self, resource_path: str, value: APIObject
    ) -> Type[ResourceClass[APIObject]]:
        resource_class = cast(
            Type[ResourceClass[APIObject]], ResourceClass.lookup(resource_path)
        )
        assert isinstance(value, resource_class.value_class)  # type: ignore
        linked = self.linked_per_type.get(resource_class.name)
        if linked is not None:
            linked.add(value)
        return resource_class


from .resourceclass import ResourceClass
