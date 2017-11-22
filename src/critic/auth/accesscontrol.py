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

import logging
import re

logger = logging.getLogger(__name__)

from critic import auth


class AccessDenied(Exception):
    """Raised by AccessControl checks on failure"""

    pass


class AccessControlError(Exception):
    """Raised in case of system configuration errors"""

    pass


class AccessControlProfile:
    @staticmethod
    async def isAllowedHTTP(req):
        def exception_applies(exception):
            if (
                exception.request_method is not None
                and exception.request_method != req.method
            ):
                return False
            if exception.path_pattern is not None and not re.match(
                exception.path_pattern, req.path
            ):
                return False
            return True

        for profile in await req.critic.session_profiles:
            category = await profile.http
            if any(exception_applies(exception) for exception in category.exceptions):
                if category.rule == "allow":
                    return False
            else:
                if category.rule == "deny":
                    return False

        return True

    @staticmethod
    async def isAllowedRepository(repository, access_type):
        def exception_applies(exception):
            if exception.repository not in (None, repository):
                return False
            if exception.access_type not in (None, access_type):
                return False
            return True

        for profile in await repository.critic.session_profiles:
            category = await profile.repositories
            if any(exception_applies(exception) for exception in category.exceptions):
                if category.rule == "allow":
                    return False
            else:
                if category.rule == "deny":
                    return False

        return True

    @staticmethod
    async def isAllowedExtension(extension, access_type):
        def exception_applies(exception):
            if exception.extension not in (None, extension):
                return False
            if exception.access_type not in (None, access_type):
                return False
            return True

        for profile in await extension.critic.session_profiles:
            category = await profile.extensions
            if any(exception_applies(exception) for exception in category.exceptions):
                if category.rule == "allow":
                    return False
            else:
                if category.rule == "deny":
                    return False

        return True


class AccessControl(object):
    @staticmethod
    async def forRequest(req):
        # Check the session status of the request.  This raises exceptions in
        # various situations.  If no exception is raised, req.user will have
        # been set, possibly to the anonymous user (or the system user.)
        await auth.checkSession(req)

    @staticmethod
    async def accessHTTP(req):
        if not await AccessControlProfile.isAllowedHTTP(req):
            raise AccessDenied("Access denied: %s /%s" % (req.method, req.path))

    class Repository(object):
        def __init__(self, repository_id, path):
            self.id = repository_id
            self.path = path

    @staticmethod
    async def accessRepository(repository, access_type):
        if not await AccessControlProfile.isAllowedRepository(repository, access_type):
            raise AccessDenied(
                "Repository access denied: %s %s" % (access_type, repository.path)
            )

    @staticmethod
    async def accessExtension(extension, access_type):
        if not await AccessControlProfile.isAllowedExtension(extension, access_type):
            raise AccessDenied(
                "Access denied to extension: %s %s" % (access_type, extension.getKey())
            )
