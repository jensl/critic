import aiohttp.web
import inspect
import logging
from typing import (
    Awaitable,
    Callable,
    Dict,
    Literal,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.background.gitaccessor.gitrepositoryproxy import GitRepositoryProxy
from critic.gitaccess.giterror import GitError


MethodHandler = Callable[
    [api.critic.Critic, Dict[str, object]], Awaitable[Union[bytes, Dict[str, object]]]
]

METHODS: Dict[str, MethodHandler] = {}


def method(version: Literal["v1"], name: str) -> Callable[[MethodHandler], None]:
    def wrapper(handler: MethodHandler) -> None:
        METHODS[f"{version}/{name}"] = handler

    return wrapper


Arguments = Dict[str, object]
T = TypeVar("T", covariant=True)
U = TypeVar("U")


class Converter(Protocol[T]):
    def __call__(self, value: object) -> Awaitable[T]:
        ...


async def maybe_await(what: Union[T, Awaitable[T]]) -> T:
    if inspect.isawaitable(what):
        return await cast(Awaitable[T], what)
    return cast(T, what)


def list_of(convert: Converter[T]) -> Converter[Sequence[T]]:
    async def wrapper(value: object) -> Sequence[T]:
        if not isinstance(value, list):
            raise ValueError("expected list")
        return [await maybe_await(convert(item)) for item in value]

    return wrapper


async def convert_argument(name: str, value: object, convert: Converter[T]) -> T:
    try:
        converted = convert(value)
        if inspect.isawaitable(converted):
            return await cast(Awaitable[T], converted)
        return cast(T, converted)
    except Exception as error:
        raise aiohttp.web.HTTPBadRequest(
            text=f"Invalid argument value: {name}: {error}"
        )


async def require_argument(arguments: Arguments, name: str, convert: Converter[T]) -> T:
    if name not in arguments:
        raise aiohttp.web.HTTPBadRequest(text=f"Missing required argument: {name}")
    return await convert_argument(name, arguments[name], convert)


async def argument(
    arguments: Arguments, name: str, convert: Converter[T]
) -> Optional[T]:
    if name not in arguments:
        return None
    return await convert_argument(name, arguments[name], convert)


async def argument_or(
    arguments: Arguments, name: str, convert: Converter[T], default: U
) -> Union[T, U]:
    if name not in arguments:
        return default
    return await convert_argument(name, arguments[name], convert)


@method("v1", "lsremote")
async def lsremote(
    critic: api.critic.Critic, arguments: Arguments
) -> Dict[str, object]:
    url: str = await require_argument(arguments, "url", str)
    refs: Sequence[str] = await argument_or(arguments, "refs", list_of(str), [])
    include_heads: bool = await argument_or(arguments, "include_head", bool, False)
    include_tags: bool = await argument_or(arguments, "include_head", bool, False)
    include_refs: bool = await argument_or(arguments, "include_head", bool, False)
    include_symbolic_refs: bool = await argument_or(
        arguments, "include_head", bool, False
    )

    async with GitRepositoryProxy.make() as repository:
        try:
            result = await repository.lsremote(
                url,
                *refs,
                include_heads=include_heads,
                include_tags=include_tags,
                include_refs=include_refs,
                include_symbolic_refs=include_symbolic_refs,
            )
        except GitError as error:
            return {"error": {"message": str(error)}}

    return {"result": {"refs": result.refs, "symbolic_refs": result.symbolic_refs}}


async def handleRequest(
    critic: api.critic.Critic, req: aiohttp.web.BaseRequest
) -> aiohttp.web.StreamResponse:
    components = req.path.strip("/").split("/", 2)

    logger.debug(f"{components=} {METHODS=}")

    if len(components) < 3 or components[0] != "api":
        raise aiohttp.web.HTTPBadRequest(text="Invalid call")

    method = METHODS.get(components[2])

    if method is None:
        raise aiohttp.web.HTTPNotFound(text=f"No such method: {components[1]!r}")

    try:
        arguments = await req.json()
    except ValueError as error:
        raise aiohttp.web.HTTPBadRequest(text=f"Invalid arguments: {error}")

    logger.debug(arguments)

    result = await method(critic, arguments)

    logger.debug(result)

    if isinstance(result, dict):
        return aiohttp.web.json_response(result)

    response = aiohttp.web.StreamResponse()

    await response.write(result)
    await response.write_eof()

    return response
