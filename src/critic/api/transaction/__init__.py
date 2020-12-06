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

import contextlib
import logging
from typing import (
    AsyncIterator,
    Optional,
    TypeVar,
    Any,
    Set,
    List,
    Type,
)

logger = logging.getLogger(__name__)

from .base import Executable, Finalizers, ReturnType, TransactionBase
from .item import Lock
from .protocol import PublishedMessage
from .types import Publisher, SimplePublisher
from .utils import requireAdministrator

from critic import api
from critic import dbaccess
from critic import pubsub

from ..impl.critic import Critic

T = TypeVar("T")

from .accesscontrolprofile.mixin import Transaction as AccessControlProfileMixin
from .accesstoken.mixin import Transaction as AccessTokenMixin
from .changeset.mixin import Transaction as ChangesetMixin
from .extension.mixin import Transaction as ExtensionMixin
from .extensioninstallation.mixin import Transaction as ExtensionInstallationMixin
from .extensionversion.mixin import Transaction as ExtensionVersionMixin
from .repository.mixin import Transaction as RepositoryMixin
from .review.mixin import Transaction as ReviewMixin
from .reviewscope.mixin import Transaction as ReviewScopeMixin
from .reviewscopefilter.mixin import Transaction as ReviewScopeFilterMixin
from .user.mixin import Transaction as UserMixin


class NoCommit(Exception):
    pass


class Savepoint:
    def __init__(
        self,
        transaction: TransactionBase,
        cursor: dbaccess.TransactionCursor,
        name: str,
    ):
        self.__transaction = transaction
        self.__cursor = cursor
        self.name = name
        self.__finalizers = Finalizers()

    @property
    def finalizers(self) -> Finalizers:
        return self.__finalizers

    async def run_finalizers(self) -> None:
        for finalizer in self.__finalizers:
            await finalizer(self.__transaction, self.__cursor)


class Transaction(
    AccessControlProfileMixin,
    AccessTokenMixin,
    ChangesetMixin,
    ExtensionMixin,
    ExtensionInstallationMixin,
    ExtensionVersionMixin,
    RepositoryMixin,
    ReviewMixin,
    ReviewScopeMixin,
    ReviewScopeFilterMixin,
    UserMixin,
    TransactionBase,
):
    __publishers: List[Publisher]
    __wakeup_services: Set[str]
    __savepoint: Optional[Savepoint]

    def __init__(
        self,
        critic: api.critic.Critic,
        cursor: dbaccess.TransactionCursor,
        pubsub_client: pubsub.Client,
        no_commit: bool,
    ) -> None:
        super().__init__(critic)
        self.__cursor = cursor
        self.__pubsub_client = pubsub_client
        self.__no_commit = no_commit
        self.tables = set()
        self.__finalizers = Finalizers()
        self.__publishers = []
        self.pre_commit_callbacks = []
        self.post_commit_callbacks = []
        self.__wakeup_services = set()
        self.__savepoint = None

    async def lock(self, table: str, **columns: dbaccess.Parameter) -> None:
        await self.execute(Lock(table).where(**columns))

    @property
    def finalizers(self) -> Finalizers:
        if self.__savepoint:
            return self.__savepoint.finalizers
        return self.__finalizers

    @property
    def has_savepoint(self) -> bool:
        return self.__savepoint is not None

    @contextlib.asynccontextmanager
    async def savepoint(self, name: str) -> AsyncIterator[Savepoint]:
        if self.__savepoint is not None:
            raise Exception(f"nested savepoints: {name} and {self.__savepoint.name}")
        async with self.__cursor.transaction.savepoint(name):
            self.__savepoint = Savepoint(self, self.__cursor, name)
            try:
                yield self.__savepoint
            finally:
                self.__savepoint = None

    def publish(
        self,
        *,
        message: Optional[PublishedMessage] = None,
        publisher: Optional[Publisher] = None,
    ) -> None:
        if message is not None:
            self.__publishers.append(SimplePublisher(message))
        if publisher is not None:
            self.__publishers.append(publisher)

    async def createLabeledAccessControlProfile(
        self, labels: Set[str], profile: api.accesscontrolprofile.AccessControlProfile
    ) -> labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return (
            await labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile.create(
                self, labels, profile
            )
        )

    def modifyLabeledAccessControlProfile(
        self,
        labeled_profile: api.labeledaccesscontrolprofile.LabeledAccessControlProfile,
    ) -> labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile:
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return labeledaccesscontrolprofile.ModifyLabeledAccessControlProfile(
            self, labeled_profile
        )

    async def createSystemSetting(
        self, key: str, description: str, value: Any, *, privileged: bool = False
    ) -> systemsetting.ModifySystemSetting:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return await systemsetting.ModifySystemSetting.create(
            self, key, description, value, privileged
        )

    def modifySystemSetting(
        self, setting: api.systemsetting.SystemSetting
    ) -> systemsetting.ModifySystemSetting:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return systemsetting.ModifySystemSetting(self, setting)

    async def addSystemEvent(
        self, category: str, key: str, title: str, data: Optional[Any] = None
    ) -> systemevent.ModifySystemEvent:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return await systemevent.ModifySystemEvent.create(
            self, category, key, title, data
        )

    def modifySystemEvent(
        self, subject: api.systemevent.SystemEvent
    ) -> systemevent.ModifySystemEvent:
        api.PermissionDenied.raiseUnlessSystem(self.critic)
        return systemevent.ModifySystemEvent(self, subject)

    # External authentication
    # =======================

    async def createExternalAccount(
        self,
        provider_name: str,
        account_id: str,
        *,
        username: Optional[str] = None,
        fullname: Optional[str] = None,
        email: Optional[str] = None,
    ) -> api.externalaccount.ExternalAccount:
        from critic import auth

        assert provider_name in auth.Provider.enabled()

        external_account = externalaccount.CreateExternalAccount(self)

        return await external_account.insert(
            provider=provider_name,
            account=account_id,
            username=username,
            fullname=fullname,
            email=email,
        )

    # Extensions
    # ==========

    # Internals
    # =========

    async def __aenter__(self) -> Transaction:
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: Any,
    ) -> None:
        if exc_type is None and exc_val is None and exc_tb is None:
            await self.__commit()

    async def __post_commit(self) -> None:
        await Critic.fromWrapper(self.critic).transactionEnded(self.critic, self.tables)
        for service_name in self.__wakeup_services:
            await self.critic.wakeup_service(service_name)
        for callback in self.post_commit_callbacks:
            await callback()

    async def __commit(self) -> None:
        self.__cursor.transaction.add_commit_callback(self.__post_commit)
        for finalizer in self.finalizers:
            await finalizer(self, self.__cursor)
        if self.__no_commit:
            raise NoCommit()
        for callback in self.pre_commit_callbacks:
            await callback()
        await self.__publish(self.__cursor)

    async def __publish(self, cursor: dbaccess.TransactionCursor) -> None:
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
            logger.debug("publish: %r", message)
            await self.__pubsub_client.publish(cursor, message)

    async def execute(self, executable: Executable[ReturnType]) -> ReturnType:
        self.tables.update(executable.table_names)
        return await executable(self, self.__cursor)

    def wakeup_service(self, service_name: str) -> None:
        self.__wakeup_services.add(service_name)


from . import externalaccount
from . import labeledaccesscontrolprofile
from . import systemevent
from . import systemsetting


@contextlib.asynccontextmanager
async def start(
    critic: api.critic.Critic,
    *,
    accept_no_pubsub: bool = False,
    no_commit: bool = False,
) -> AsyncIterator[Transaction]:
    try:
        async with pubsub.connect(
            "api.transaction", mode="lazy", accept_failure=accept_no_pubsub
        ) as pubsub_client:
            async with critic.transaction() as cursor:
                async with Transaction(
                    critic, cursor, pubsub_client, no_commit
                ) as transaction:
                    yield transaction
    except NoCommit:
        pass


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
    # item.py
    "Item",
    "Query",
    "Insert",
    "InsertMany",
    "Update",
    "Delete",
    "Verify",
    "requireAdministrator",
]
