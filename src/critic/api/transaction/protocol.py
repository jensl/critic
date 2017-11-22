from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Sequence, Union

from critic import pubsub


@dataclass
class APIObjectBase:
    resource_name: str
    object_id: int

    def scopes(self) -> Sequence[pubsub.ChannelName]:
        return (pubsub.ChannelName(f"{self.resource_name}/{self.object_id}"),)

    def serialize(self) -> Dict[str, Any]:
        return {
            key: getattr(self, key) for key in getattr(self, "__dataclass_fields__")
        }


@dataclass
class CreatedAPIObject(APIObjectBase):
    action: str = field(default="created", init=False)


@dataclass
class CreatedSystemEvent(CreatedAPIObject):
    category: str
    key: str
    title: str
    data: Any


@dataclass
class CreatedSystemSetting(CreatedAPIObject):
    key: str


@dataclass
class CreatedBranch(CreatedAPIObject):
    repository_id: int
    name: str


@dataclass
class CreatedReviewObject(CreatedAPIObject):
    review_id: int


@dataclass
class CreatedReviewEvent(CreatedReviewObject):
    event_type: str


@dataclass
class CreatedUserEmail(CreatedAPIObject):
    user_id: int


@dataclass
class ModifiedAPIObject(APIObjectBase):
    action: str = field(default="modified", init=False)
    updates: Mapping[str, Any]


@dataclass
class ModifiedSystemSetting(ModifiedAPIObject):
    key: str


@dataclass
class DeletedAPIObject(APIObjectBase):
    action: str = field(default="deleted", init=False)


@dataclass
class DeletedRepository(DeletedAPIObject):
    name: str
    path: str


PublishedMessage = Union[CreatedAPIObject, ModifiedAPIObject, DeletedAPIObject]
