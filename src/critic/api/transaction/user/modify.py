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

import re
from typing import Collection, Optional, Union, Iterable, Any

from . import CreatedUser
from .. import Transaction, Query, Insert, Update, Modifier

from critic import api


class ModifyUser(Modifier[api.user.User, CreatedUser]):
    def __init__(
        self, transaction: Transaction, user: Union[api.user.User, CreatedUser]
    ) -> None:
        super().__init__(transaction, user)
        if not isinstance(user, CreatedUser):
            transaction.lock("users", id=user.id)

    def setFullname(self, value: str) -> None:
        self.transaction.items.append(Update(self.subject).set(fullname=value))

    def setStatus(self, value: api.user.Status) -> None:
        set_status(self.transaction, self.subject, value)

    def setPassword(self, *, hashed_password: str) -> None:
        self.transaction.items.append(
            Update(self.subject).set(password=hashed_password)
        )

    # Roles
    # =====

    def addRole(self, role: str) -> None:
        api.PermissionDenied.raiseUnlessSystem(self.transaction.critic)
        self.transaction.items.append(
            Insert("userroles").values(uid=self.subject, role=role)
        )

    def deleteRole(self, role: str) -> None:
        api.PermissionDenied.raiseUnlessSystem(self.transaction.critic)
        self.transaction.items.append(
            Query(
                """DELETE
                     FROM userroles
                    WHERE uid={user}
                      AND role={role}""",
                user=self.subject,
                role=role,
            )
        )

    # Repository filters
    # ==================

    def createFilter(
        self,
        filter_type: api.repositoryfilter.FilterType,
        repository: api.repository.Repository,
        path: str,
        default_scope: bool,
        scopes: Iterable[api.reviewscope.ReviewScope],
        delegates: Iterable[api.user.User],
    ) -> ModifyRepositoryFilter:
        return ModifyRepositoryFilter.create(
            self.transaction,
            self.real,
            filter_type,
            repository,
            path,
            default_scope,
            scopes,
            delegates,
        )

    async def modifyFilter(
        self, repository_filter: api.repositoryfilter.RepositoryFilter
    ) -> ModifyRepositoryFilter:
        if await repository_filter.subject != self.subject:
            raise api.user.Error(
                "Cannot modify repository filter belonging to another user"
            )
        return ModifyRepositoryFilter(self.transaction, repository_filter)

    # Access tokens
    # =============

    def createAccessToken(self, title: Optional[str]) -> ModifyAccessToken:
        if self.transaction.critic.access_token:
            # Don't allow creation of access tokens when an access token was
            # used to authenticate.  This could be used to effectively bypass
            # access restrictions set on the access token, unless we make sure
            # the created access token's access control profile is at least
            # equally strict, which is difficult.
            raise api.PermissionDenied("Access token used to authenticate")

        return ModifyAccessToken.create(self.transaction, "user", title, user=self.real)

    async def modifyAccessToken(
        self, access_token: api.accesstoken.AccessToken
    ) -> ModifyAccessToken:
        from ..accesstoken import ModifyAccessToken

        if await access_token.user != self.subject:
            raise api.PermissionDenied(
                "Cannot modify access token belonging to another user"
            )

        if self.transaction.critic.access_token:
            # Don't allow any modifications of access tokens when an access
            # token was used to authenticate.  This could be used to effectively
            # bypass access restrictions set on the access token, unless we make
            # sure the modified access token's access control profile is at
            # least equally strict, which is difficult.
            raise api.PermissionDenied("Access token used to authenticate")

        return ModifyAccessToken(self.transaction, access_token)

    # User settings
    # =============

    async def defineSetting(
        self, scope: str, name: str, value: Any
    ) -> ModifyUserSetting:
        return await ModifyUserSetting.create(
            self.transaction, self.subject, scope, name, value
        )

    async def modifyUserSetting(
        self, usersetting: api.usersetting.UserSetting
    ) -> ModifyUserSetting:
        if self.subject != await usersetting.user:
            raise api.user.Error(
                "Cannot modify a user setting belonging to another user"
            )
        return ModifyUserSetting(self.transaction, usersetting)

    # External authentication
    # =======================

    def connectTo(self, external_account: api.externalaccount.ExternalAccount) -> None:
        self.transaction.items.append(Update(external_account).set(uid=self.subject))

    # Email addresses
    # ===============

    def addEmailAddress(
        self, address: str, *, status: api.useremail.Status = "unverified"
    ) -> ModifyUserEmail:
        return ModifyUserEmail.create(self.transaction, self.subject, address, status)

    async def modifyEmailAddress(
        self, useremail: api.useremail.UserEmail
    ) -> ModifyUserEmail:
        if self.subject != await useremail.user:
            raise api.user.Error("Cannot modify user email belonging to another user")
        return ModifyUserEmail(self.transaction, useremail)

    # SSH keys
    # ========

    def addSSHKey(
        self, key_type: str, key: str, comment: str = None
    ) -> ModifyUserSSHKey:
        return ModifyUserSSHKey.create(
            self.transaction, self.subject, key_type, key, comment
        )

    async def modifySSHKey(
        self, usersshkey: api.usersshkey.UserSSHKey
    ) -> ModifyUserSSHKey:
        if self.subject != await usersshkey.user:
            raise api.user.Error("Cannot modify another user's SSH key")
        return ModifyUserSSHKey(self.transaction, usersshkey)

    # Extensions
    # ==========

    async def createExtension(self, name: str, uri: str) -> ModifyExtension:
        return await ModifyExtension.create(
            self.transaction, name, uri, publisher=self.real
        )

    async def modifyExtension(
        self, extension: api.extension.Extension
    ) -> ModifyExtension:
        if self.subject != await extension.publisher:
            raise api.user.Error("Cannot modify extension published by another user")
        return ModifyExtension(self.transaction, extension, self.real)

    async def installExtension(
        self,
        extension: api.extension.Extension,
        version: api.extensionversion.ExtensionVersion,
    ) -> ModifyExtensionInstallation:
        return await ModifyExtensionInstallation.create(
            self.transaction, extension, version, user=self.real
        )

    async def modifyExtensionInstallation(
        self, installation: api.extensioninstallation.ExtensionInstallation
    ) -> ModifyExtensionInstallation:
        if await installation.user != self.real:
            raise api.user.Error(
                "Cannot modify extension installation beloning to another user"
            )
        return ModifyExtensionInstallation(self.transaction, installation)

    @staticmethod
    def create(
        transaction: Transaction,
        name: str,
        fullname: str,
        email: Optional[str],
        email_status: Optional[api.useremail.Status],
        hashed_password: Optional[str],
        status: api.user.Status,
        external_account: Optional[api.externalaccount.ExternalAccount],
    ) -> ModifyUser:
        modifier = ModifyUser(
            transaction,
            create_user(
                transaction,
                name,
                fullname,
                email,
                email_status,
                hashed_password,
                status,
                external_account,
            ),
        )

        if external_account is not None:
            modifier.connectTo(external_account)

            if (
                transaction.critic.session_type == "user"
                and transaction.critic.actual_user is None
            ):
                # "Upgrade" existing user sessions (typically just the current one)
                # to belong to the newly created user.
                transaction.items.append(
                    Update("usersessions")
                    .set(uid=modifier.subject)
                    .where(external_uid=external_account)
                )

        return modifier


from .create import create_user
from .setstatus import set_status
from ..accesstoken import ModifyAccessToken
from ..extension import ModifyExtension
from ..extensioninstallation import ModifyExtensionInstallation
from ..repositoryfilter import CreatedRepositoryFilter, ModifyRepositoryFilter
from ..useremail import ModifyUserEmail
from ..usersetting import ModifyUserSetting
from ..usersshkey import ModifyUserSSHKey
