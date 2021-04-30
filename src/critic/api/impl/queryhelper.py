from dataclasses import dataclass
import logging
from typing import (
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
    overload,
)

logger = logging.getLogger(__name__)

from critic import api, dbaccess


RowType = TypeVar("RowType")
ObjectType = TypeVar("ObjectType")


@dataclass
class Query:
    __source: str

    def __str__(self) -> str:
        return self.__source


class ValueExceptionFactory(Protocol):
    def __call__(self, *, value: object) -> api.APIError:
        ...


class ValuesExceptionFactory(Protocol):
    def __call__(self, *, values: Iterable[object]) -> api.APIError:
        ...


def join(**tables: Sequence[str]) -> str:
    assert len(tables) == 1
    ((table_name, conditions),) = tables.items()
    assert len(conditions) > 0
    return f"JOIN {table_name} ON ({' AND '.join(conditions)})"


def left_outer_join(**tables: Sequence[str]) -> str:
    assert len(tables) == 1
    ((table_name, conditions),) = tables.items()
    assert len(conditions) > 0
    return f"LEFT OUTER JOIN {table_name} ON ({' AND '.join(conditions)})"


def formatCondition(column: str, value: dbaccess.Parameter) -> str:
    if isinstance(value, (list, tuple)):
        return f"{column}=ANY({{{column}}})"
    return f"{column}={{{column}}}"


def exists(**tables: Sequence[str]) -> str:
    assert len(tables) == 1
    ((table_name, conditions),) = tables.items()
    return f"""EXISTS (
        SELECT 1
          FROM {table_name}
         WHERE ({') AND ('.join(conditions)})
         LIMIT 1
    )"""


class QueryResult(Generic[RowType]):
    def __init__(
        self,
        critic: api.critic.Critic,
        query: AsyncContextManager[dbaccess.ResultSet[RowType]],
    ):
        self.__critic = critic
        self.__query = query

    async def makeOne(
        self,
        factory: Callable[[api.critic.Critic, RowType], ObjectType],
        error: Optional[Exception] = None,
    ) -> ObjectType:
        try:
            async with self.__query as result:
                return factory(self.__critic, await result.one())
        except dbaccess.ZeroRowsInResult:
            if error:
                raise error
            raise

    async def make(
        self,
        factory: Callable[[api.critic.Critic, RowType], ObjectType],
    ) -> Sequence[ObjectType]:
        objects = []
        async with self.__query as result:
            async for args in result:
                objects.append(factory(self.__critic, args))
        return objects

    async def __aenter__(self) -> dbaccess.ResultSet[RowType]:
        return await self.__query.__aenter__()

    async def __aexit__(self, *args: Any) -> None:
        await self.__query.__aexit__(*args)


class QueryHelper(Generic[RowType]):
    def __init__(
        self,
        table_name: str,
        *column_names: str,
        id_column: Optional[str] = None,
        default_order_by: Optional[Sequence[str]] = None,
        default_joins: Sequence[str] = [],
    ):
        self.table_name = table_name
        self.column_names = column_names
        self.id_column = id_column or column_names[0]
        self.default_order_by = default_order_by or [f"{self.id_column} ASC"]
        self.default_joins = default_joins

    @property
    def columns(self) -> str:
        return ", ".join(
            column_name if "." in column_name else f"{self.table_name}.{column_name}"
            for column_name in self.column_names
        )

    def formatQuery(
        self,
        *conditions: str,
        order_by: Optional[Sequence[str]] = None,
        joins: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        distinct_on: Optional[Sequence[str]] = None,
    ) -> Query:
        if distinct_on is None:
            use_distinct_on = ""
        else:
            use_distinct_on = f" DISTINCT ON ({', '.join(distinct_on)})"
        clauses: List[Optional[str]] = [
            f"SELECT{use_distinct_on} {self.columns}",
            f"FROM {self.table_name}",
        ]
        if joins is None:
            joins = self.default_joins
        clauses.extend(joins)
        if conditions:
            clauses.append(f"WHERE ({') AND ('.join(conditions)})")
        if not order_by:
            order_by = self.default_order_by
        if order_by:
            clauses.append(f"ORDER BY {', '.join(order_by)}")
        if limit is not None:
            clauses.append(f"LIMIT {limit}")
        return Query(" ".join(filter(None, clauses)))

    @overload
    def query(
        self,
        critic: api.critic.Critic,
        query: Query,
        /,
        **parameters: dbaccess.Parameter,
    ) -> QueryResult[RowType]:
        ...

    @overload
    def query(
        self,
        critic: api.critic.Critic,
        /,
        *conditions: str,
        **parameters: dbaccess.Parameter,
    ) -> QueryResult[RowType]:
        ...

    def query(
        self,
        critic: api.critic.Critic,
        query_or_condition: Optional[Union[str, Query]] = None,
        /,
        *conditions: str,
        **parameters: dbaccess.Parameter,
    ) -> QueryResult[RowType]:
        if isinstance(query_or_condition, Query):
            query = query_or_condition
        else:
            all_conditions = [*conditions]
            if isinstance(query_or_condition, str):
                all_conditions.insert(0, query_or_condition)
            if not all_conditions:
                all_conditions.extend(
                    formatCondition(key, value)
                    for key, value in parameters.items()
                    if value is not None
                )
            query = self.formatQuery(*all_conditions)
        # logger.debug("%s %r", query, parameters)
        return QueryResult(
            critic, api.critic.Query[RowType](critic, str(query), **parameters)
        )

    def queryById(
        self,
        critic: api.critic.Critic,
        value: int,
        /,
    ) -> QueryResult[RowType]:
        return self.query(
            critic,
            self.formatQuery(f"{self.table_name}.{self.id_column}={{value}}"),
            value=value,
        )

    def queryByIds(
        self,
        critic: api.critic.Critic,
        values: Sequence[int],
        /,
    ) -> QueryResult[RowType]:
        return self.query(
            critic,
            self.formatQuery(f"{self.table_name}.{self.id_column}=ANY({{values}})"),
            values=values,
        )

    def idFetcher(
        self,
        critic: api.critic.Critic,
        factory: Callable[[api.critic.Critic, RowType], ObjectType],
    ) -> Callable[[int], Awaitable[ObjectType]]:
        async def idFetcher(value: int) -> Any:
            return await self.queryById(critic, value).makeOne(factory)

        return idFetcher

    def idsFetcher(
        self,
        critic: api.critic.Critic,
        factory: Callable[[api.critic.Critic, RowType], ObjectType],
    ) -> Callable[[Sequence[int]], Awaitable[Sequence[ObjectType]]]:
        async def idsFetcher(values: Sequence[int]) -> Sequence[Any]:
            return await self.queryByIds(critic, values).make(factory)

        return idsFetcher

    def itemFetcher(
        self,
        critic: api.critic.Critic,
        factory: Callable[[api.critic.Critic, RowType], ObjectType],
        name: str,
        error: Optional[Exception] = None,
    ) -> Callable[[dbaccess.Parameter], Awaitable[ObjectType]]:
        async def itemFetcher(value: dbaccess.Parameter) -> Any:
            return await self.query(critic, **{name: value}).makeOne(factory, error)

        return itemFetcher

    def itemsFetcher(
        self,
        critic: api.critic.Critic,
        factory: Callable[[api.critic.Critic, RowType], ObjectType],
        name: str,
    ) -> Callable[[Sequence[dbaccess.SQLAtom]], Awaitable[Sequence[ObjectType]]]:
        async def itemsFetcher(values: Sequence[dbaccess.SQLAtom]) -> Sequence[Any]:
            return await self.query(critic, **{name: values}).make(factory)

        return itemsFetcher
