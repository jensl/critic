# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import functools
import json
import logging
import types
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
    Generic,
    Type,
    Generator,
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
from .item import Item, Items, Query, Insert, InsertMany, Update, Delete, Verify
from .types import Publisher, SimplePublisher, AsyncCallback
from .utils import requireAdministrator, requireSystem
from .protocol import (
    CreatedAPIObject,
    ModifiedAPIObject,
    DeletedAPIObject,
    PublishedMessage,
)

# from .transaction import Transaction

from critic import api
from critic import base
from critic import dbaccess
from critic import pubsub

T = TypeVar("T")


class Shared:
    __items: Dict[Any, Any]

    def __init__(self) -> None:
        self.__items = {}

    def __iter__(self) -> Iterator[Any]:
        return iter(self.__items.keys())

    def ensure(self, item: T) -> T:
        if item not in self.__items:
            self.__items[item] = item
        return self.__items[item]


class Transaction:
    tables: Set[str]
    __locks: Dict[Tuple[str, str], Set[dbaccess.Parameter]]
    __publishers: List[Publisher]
    pre_commit_callbacks: List[AsyncCallback]
    post_commit_callbacks: List[AsyncCallback]
    __wakeup_services: Set[str]

    def __init__(self, critic: api.critic.Critic, accept_no_pubsub: bool) -> None:
        self.critic = critic
        self.accept_no_pubsub = accept_no_pubsub
        self.tables = set()
        self.__locks = defaultdict(set)
        self.__publishers = []
        self.shared = Shared()
        self.items = Items(self)
        self.finalizers = Finalizers(self)
        self.pre_commit_callbacks = []
        self.post_commit_callbacks = []
        self.__wakeup_services = set()

    def lock(self, table: str, **columns: dbaccess.Parameter) -> None:
        assert len(columns) == 1
        self.tables.add(table)
        [(column, value)] = columns.items()
        query = f"SELECT {column} FROM {table} WHERE {{{column}:array}}"
        self.__locks[(query, column)].add(value)

    def publish(
        self,
        *,
        message: PublishedMessage = None,
        publisher: Publisher = None,
    ) -> None:
        if message is not None:
            self.__publishers.append(SimplePublisher(message))
        if publisher is not None:
            self.__publishers.append(publisher)

    async def createUser(
        self,
        name: str,
        fullname: str,
        email: Optional[str],
        *,
        email_status: api.useremail.Status = None,
        hashed_password: str = None,
        status: api.user.Status = "current",
        external_account: api.externalaccount.ExternalAccount = None,
    ) -> user.ModifyUser:
        # Note: Access control is in create_user(), as it is non-trivial.
        return user.ModifyUser.create(
            self,
            name,
            fullname,
            email,
            email_status,
            hashed_password,
            status,
            external_account,
        )

    def modifyUser(self, subject: api.user.User) -> user.ModifyUser:
        api.PermissionDenied.raiseUnlessUser(self.critic, subject)
        return user.ModifyUser(self, subject)

    def createAccessToken(
        self, access_type: api.accesstoken.AccessType, title: Optional[str]
    ) -> accesstoken.ModifyAccessToken:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return accesstoken.ModifyAccessToken.create(self, access_type, title)

    def modifyAccessToken(
        self,
        access_token: Union[
            api.accesstoken.AccessToken, accesstoken.CreatedAccessToken
        ],
    ) -> accesstoken.ModifyAccessToken:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return accesstoken.ModifyAccessToken(self, access_token)

    def createAccessControlProfile(
        self,
    ) -> accesscontrolprofile.ModifyAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return accesscontrolprofile.ModifyAccessControlProfile.create(self)

    def modifyAccessControlProfile(
        self, profile: api.accesscontrolprofile.AccessControlProfile
    ) -> accesscontrolprofile.ModifyAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return accesscontrolprofile.ModifyAccessControlProfile(self, profile)

    def createLabeledAccessControlProfile(
        self, labels: Set[str], profile: api.accesscontrolprofile.AccessControlProfile
    ) -> labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile.create(
            self, labels, profile
        )

    def modifyLabeledAccessControlProfile(
        self,
        labeled_profile: api.labeledaccesscontrolprofile.LabeledAccessControlProfile,
    ) -> labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile(
            self, labeled_profile
        )

    @requireSystem
    def createRepository(self, name: str, path: str) -> repository.ModifyRepository:
        return repository.ModifyRepository.create(self, name, path)

    # FIXME: Should require write-access to the repository.
    def modifyRepository(
        self, subject: api.repository.Repository
    ) -> repository.ModifyRepository:
        return repository.ModifyRepository(self, subject)

    async def createReview(
        self,
        repository: api.repository.Repository,
        owners: Iterable[api.user.User],
        *,
        head: api.commit.Commit = None,
        commits: Iterable[api.commit.Commit] = None,
        branch: Union[api.branch.Branch, branch.CreatedBranch] = None,
        target_branch: api.branch.Branch = None,
        via_push: bool = False,
    ) -> review.ModifyReview:
        return await review.ModifyReview.create(
            self, repository, owners, head, commits, branch, target_branch, via_push
        )

    def modifyReview(self, subject: api.review.Review) -> review.ModifyReview:
        return review.ModifyReview(self, subject)

    def createReviewScope(self, name: str) -> reviewscope.ModifyReviewScope:
        return reviewscope.ModifyReviewScope.create(self, name)

    def modifyReviewScope(
        self, scope: api.reviewscope.ReviewScope
    ) -> reviewscope.ModifyReviewScope:
        return reviewscope.ModifyReviewScope(self, scope)

    def createReviewScopeFilter(
        self,
        repository: api.repository.Repository,
        scope: Union[api.reviewscope.ReviewScope, reviewscope.CreatedReviewScope],
        path: str,
        included: bool,
    ) -> reviewscopefilter.ModifyReviewScopeFilter:
        return reviewscopefilter.ModifyReviewScopeFilter.create(
            self, repository, scope, path, included
        )

    def modifyReviewScopeFilter(
        self, scope_filter: api.reviewscopefilter.ReviewScopeFilter
    ) -> reviewscopefilter.ModifyReviewScopeFilter:
        return reviewscopefilter.ModifyReviewScopeFilter(self, scope_filter)

    async def ensureChangeset(
        self,
        from_commit: Optional[api.commit.Commit],
        to_commit: api.commit.Commit,
        *,
        conflicts: bool,
    ) -> changeset.ModifyChangeset:
        return await changeset.ModifyChangeset.ensure(
            self, from_commit, to_commit, conflicts
        )

    def createSystemSetting(
        self, key: str, description: str, value: Any, *, privileged: bool = False
    ) -> systemsetting.ModifySystemSetting:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return systemsetting.ModifySystemSetting.create(
            self, key, description, value, privileged
        )

    def modifySystemSetting(
        self, setting: api.systemsetting.SystemSetting
    ) -> systemsetting.ModifySystemSetting:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return systemsetting.ModifySystemSetting(self, setting)

    def addSystemEvent(
        self, category: str, key: str, title: str, data: Any = None
    ) -> systemevent.ModifySystemEvent:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return systemevent.ModifySystemEvent.create(self, category, key, title, data)

    def modifySystemEvent(
        self, subject: api.systemevent.SystemEvent
    ) -> systemevent.ModifySystemEvent:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return systemevent.ModifySystemEvent(self, subject)

    # External authentication
    # =======================

    def createExternalAccount(
        self,
        provider_name: str,
        account_id: str,
        *,
        username: str = None,
        fullname: str = None,
        email: str = None,
    ) -> externalaccount.CreatedExternalAccount:
        from critic import auth

        assert provider_name in auth.Provider.enabled()

        external_account = externalaccount.CreatedExternalAccount(self)

        self.tables.add("externalusers")
        self.items.append(
            Insert("externalusers", returning="id", collector=external_account).values(
                provider=provider_name,
                account=account_id,
                username=username,
                fullname=fullname,
                email=email,
            )
        )

        return external_account

    # Extensions
    # ==========

    async def createExtension(self, name: str, uri: str) -> extension.ModifyExtension:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return await extension.ModifyExtension.create(self, name, uri)

    async def modifyExtension(
        self, subject: api.extension.Extension
    ) -> extension.ModifyExtension:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return extension.ModifyExtension(self, subject, None)

    async def installExtension(
        self,
        extension: api.extension.Extension,
        version: api.extensionversion.ExtensionVersion,
    ) -> extensioninstallation.ModifyExtensionInstallation:
        return await extensioninstallation.ModifyExtensionInstallation.create(
            self, extension, version
        )

    async def modifyExtensionInstallation(
        self, installation: api.extensioninstallation.ExtensionInstallation
    ) -> extensioninstallation.ModifyExtensionInstallation:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        if not installation.is_universal:
            raise api.APIError("installation is not universal")
        return extensioninstallation.ModifyExtensionInstallation(self, installation)

    # Internals
    # =========

    async def __aenter__(self) -> Transaction:
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: types.TracebackType,
    ) -> None:
        if exc_type is None and exc_val is None and exc_tb is None:
            await self.__commit()

    async def __commit(self) -> None:
        if not self.items:
            logger.debug("empty API transaction")
            return
        try:
            pubsub_connection = pubsub.connect(
                "api.transaction", mode="lazy", accept_failure=self.accept_no_pubsub
            )
            transaction = self.critic.database.transaction()
            async with pubsub_connection as pubsub_client, transaction as cursor:
                for (query, column), values in self.__locks.items():
                    logger.debug("locking: %r %s=%r", query, column, values)
                    async with cursor.query(
                        query, **{column: list(values)}, for_update=True
                    ) as result:
                        await result.ignore()
                items = self.items.take()
                while items:
                    item = items.pop(0)
                    logger.debug("executing item: %r", item)
                    try:
                        await item(self, cursor)
                    except api.APIError:
                        raise
                    except Exception:
                        logger.exception("Transaction item failed: %r", item)
                        raise
                    items[0:0] = self.items.take()
                for finalizer in self.finalizers:
                    await finalizer(self, cursor)
                for callback in self.pre_commit_callbacks:
                    await callback()
                await self.__publish(cursor, pubsub_client)
            for callback in self.post_commit_callbacks:
                await callback()
        finally:
            await self.critic._impl.transactionEnded(self.critic, self.tables)
            for service_name in self.__wakeup_services:
                await self.critic.wakeup_service(service_name)

    async def __publish(
        self, cursor: dbaccess.TransactionCursor, pubsub_client: pubsub.Client
    ) -> None:
        messages: List[pubsub.PublishMessage] = []

        for provider in self.__publishers:
            publish_details = await provider.publish()
            if publish_details is None:
                continue
            channel_names, payload = publish_details
            messages.append(
                pubsub.PublishMessage(channel_names, pubsub.Payload(payload))
            )

        for message in messages:
            await pubsub_client.publish(cursor, message)

    def wakeup_service(self, service_name: str) -> None:
        self.__wakeup_services.add(service_name)


class Finalizer:
    tables: Iterable[str] = ()

    def should_run_after(self, other: Finalizer) -> bool:
        return False

    async def __call__(
        self, transaction: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        raise Exception("Finalizer sub-class must override `__call__`")


class Finalizers:
    __items: List[Finalizer]
    __items_set: Set[Finalizer]

    def __init__(self, transaction: Transaction) -> None:
        self.__transaction = transaction
        self.__items = []
        self.__items_set = set()

    def __iter__(self) -> Iterator[Finalizer]:
        queue = deque(self.__items)
        while queue:
            item = queue.popleft()
            if any(item.should_run_after(other) for other in queue):
                queue.append(item)
                continue
            yield item

    def add(self, finalizer: Finalizer) -> bool:
        if finalizer in self.__items_set:
            return False
        self.__transaction.tables.update(finalizer.tables)
        self.__items.append(finalizer)
        self.__items_set.add(finalizer)
        return True


APIObjectType = TypeVar("APIObjectType", bound=api.APIObject)
CreatedObjectType = TypeVar("CreatedObjectType", bound=LazyAPIObject)


class Modifier(Generic[APIObjectType, CreatedObjectType]):
    updates: Dict[str, Any]

    def __init__(
        self, transaction: Transaction, subject: Union[APIObjectType, CreatedObjectType]
    ) -> None:
        self.transaction = transaction
        self.transaction.publish(publisher=self)
        self.subject = subject
        self.updates = {}
        self.modified = False
        self.deleted = False

    @property
    def is_real(self) -> bool:
        return isinstance(self.subject, api.APIObject)

    @property
    def real(self) -> APIObjectType:
        assert isinstance(self.subject, api.APIObject)
        return cast(APIObjectType, self.subject)

    @property
    def is_created(self) -> bool:
        return isinstance(self.subject, LazyAPIObject)

    @property
    def created(self) -> CreatedObjectType:
        assert isinstance(self.subject, LazyAPIObject)
        return cast(CreatedObjectType, self.subject)

    @property
    def resource_name(self) -> str:
        if isinstance(self.subject, api.APIObject):
            return self.subject.getResourceName()
        assert self.created.resource_name
        return self.created.resource_name

    @property
    def subject_id(self) -> int:
        if isinstance(self.subject, api.APIObject):
            return self.subject.id
        return int(self.created)

    def __await__(self) -> Generator[Any, None, APIObjectType]:
        if isinstance(self.subject, LazyAPIObject):
            return self.subject.future.__await__()

        async def real() -> APIObjectType:
            return self.real

        return real().__await__()

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.subject))
        self.deleted = True

    async def publish(
        self,
    ) -> Optional[Tuple[Sequence[pubsub.ChannelName], PublishedMessage]]:
        resource_name = self.resource_name
        object_id = self.subject_id
        if object_id is None:
            return None

        message: PublishedMessage
        if self.deleted:
            message = await self.create_deleted_payload()
        elif self.modified or self.updates:
            message = await self.create_modified_payload()
        else:
            return None

        return (
            [pubsub.ChannelName(f"{resource_name}/{object_id}")],
            message,
        )

    async def create_modified_payload(self) -> ModifiedAPIObject:
        return ModifiedAPIObject(self.resource_name, self.subject_id, self.updates)

    async def create_deleted_payload(self) -> DeletedAPIObject:
        return DeletedAPIObject(self.resource_name, self.subject_id)


from . import accesscontrolprofile
from . import accesstoken
from . import branch
from . import extension
from . import extensioninstallation
from . import externalaccount
from . import labeledaccesscontrolprofile
from . import repository
from . import review
from . import reviewscope
from . import reviewscopefilter
from . import systemevent
from . import systemsetting
from . import user
from . import changeset


def start(critic: api.critic.Critic, *, accept_no_pubsub: bool = False) -> Transaction:
    return Transaction(critic, accept_no_pubsub)


# class PublishedMessage:
#     def __init__(self, *channels: str, **items: Any):
#         self.__channels = channels
#         self.__items = items

#     def publish(self) -> Optional[Tuple[Sequence[str], dict]]:
#         def process(item: Any) -> Any:
#             if isinstance(item, LazyInt):
#                 return int(item)
#             return item

#         return (
#             self.__channels,
#             {key: process(item) for key, item in self.__items.items()},
#         )


__all__ = [
    # lazy.py
    "Result",
    "LazyValue",
    "LazyInt",
    "LazyObject",
    "LazyAPIObject",
    "GenericLazyAPIObject",
    "CollectCreatedObject",
    # item.py
    "Item",
    "Query",
    "Insert",
    "InsertMany",
    "Update",
    "Delete",
    "Verify",
]
