import datetime
from typing import Optional, Union, Awaitable, overload

EPOCH = datetime.datetime.fromtimestamp(0)
EPOCH_UTC = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)


Timestamp = Union[
    datetime.datetime,
    Awaitable[datetime.datetime],
]
OptionalTimestamp = Union[
    Optional[datetime.datetime],
    Awaitable[Optional[datetime.datetime]],
]


@overload
async def timestamp(timestamp: Timestamp) -> float:
    ...


@overload
async def timestamp(timestamp: OptionalTimestamp) -> Optional[float]:
    ...


async def timestamp(timestamp: OptionalTimestamp) -> Optional[float]:
    if timestamp and not isinstance(timestamp, datetime.datetime):
        timestamp = await timestamp
    if timestamp is None:
        return None
    assert isinstance(timestamp, datetime.datetime)
    if timestamp.tzinfo:
        return (timestamp - EPOCH_UTC).total_seconds()
    return (timestamp - EPOCH).total_seconds()
