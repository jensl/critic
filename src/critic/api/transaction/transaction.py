from __future__ import annotations

import functools
import json
import logging
from collections import defaultdict, deque
from typing import (
    Optional,
    TypeVar,
    Callable,
    Any,
    Dict,
    Set,
    List,
    Tuple,
    Protocol,
    Sequence,
    Coroutine,
    Iterator,
    Iterable,
    Union,
    cast,
)

logger = logging.getLogger(__name__)

from .lazy import (
    Result,
    LazyValue,
    LazyInt,
    LazyObject,
    LazyAPIObject,
    GenericLazyAPIObject,
    CollectCreatedObject,
)
from .item import (
    Item,
    Items,
    Query,
    Insert,
    InsertMany,
    Update,
    Delete,
    Verify,
)
from .types import Publisher, AsyncCallback
from .utils import requireAdministrator, requireSystem

from critic import api
from critic import base
from critic import dbaccess
