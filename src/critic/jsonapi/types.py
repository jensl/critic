from __future__ import annotations

from typing import (
    Any,
    Optional,
    Protocol,
    TypeVar,
    Union,
    List,
    Dict,
)

from multidict import MultiDictProxy


T = TypeVar("T")


JSONInputAtom = Optional[Union[bool, float, str]]
JSONInputItem4 = JSONInputAtom
JSONInputItem3 = Union[JSONInputAtom, List[JSONInputItem4], Dict[str, JSONInputItem4]]
JSONInputItem2 = Union[JSONInputAtom, List[JSONInputItem3], Dict[str, JSONInputItem3]]
JSONInputItem1 = Union[JSONInputAtom, List[JSONInputItem2], Dict[str, JSONInputItem2]]
JSONInputItem = Union[JSONInputAtom, List[JSONInputItem1], Dict[str, JSONInputItem1]]
JSONInput = Dict[str, JSONInputItem1]

# JSONResultAtom = Optional[Union[bool, float, str, api.APIObject]]
# JSONResultItem4 = JSONResultAtom
# JSONResultItem3 = Union[
#     JSONResultAtom,
#     Mapping[str, JSONResultItem4],
#     Collection[JSONResultItem4],
#     Awaitable[JSONResultItem4],
#     Optional[ValueWrapper[JSONResultItem4]],
# ]
# JSONResultItem2 = Union[
#     JSONResultAtom,
#     Mapping[str, JSONResultItem3],
#     Collection[JSONResultItem3],
#     Awaitable[JSONResultItem3],
#     Optional[ValueWrapper[JSONResultItem3]],
# ]
# JSONResultItem1 = Union[
#     JSONResultAtom,
#     Mapping[str, JSONResultItem2],
#     Collection[JSONResultItem2],
#     Awaitable[JSONResultItem2],
#     Optional[ValueWrapper[JSONResultItem2]],
# ]
# JSONResult1 = Mapping[str, JSONResultItem1]
# JSONResultItem = Union[
#     JSONResultAtom,
#     JSONResult1,
#     Collection[JSONResultItem1],
#     Awaitable[JSONResultItem1],
#     ValueWrapper[JSONResultItem1],
# ]
# JSONResult = Mapping[str, JSONResultItem]

JSONResultItem = Any
JSONResult = Any


class Request(Protocol):
    method: str
    scheme: str
    path: str

    query: MultiDictProxy[str]

    async def read(self) -> str:
        ...
