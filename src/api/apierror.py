# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

class APIError(Exception):
    """Base exception for all errors caused by incorrect API usage (including
       invalid input.)"""
    pass

class PermissionDenied(Exception):
    """Exception raised on correct API usage that the current user is not
       allowed."""

    @staticmethod
    def raiseUnlessAdministrator(critic):
        if not (critic.actual_user and
                critic.actual_user.hasRole("administrator")):
            raise PermissionDenied("Must be an administrator")

    @staticmethod
    def raiseUnlessUser(critic, required_user):
        if critic.actual_user != required_user:
            PermissionDenied.raiseUnlessAdministrator(critic)

class TransactionError(APIError):
    """Base exception for transaction errors."""
    pass
