# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

from operation import Operation, OperationResult, OperationError, Optional
from extensions.installation import installExtension, uninstallExtension, reinstallExtension

class ExtensionOperation(Operation):
    def __init__(self, perform):
        Operation.__init__(self, { "author_name": str,
                                   "extension_name": str,
                                   "version": Optional(str) })
        self.perform = perform

    def process(self, db, user, author_name, extension_name, version=None):
        if version is not None:
            if version == "live": version = None
            elif version.startswith("version/"): version = version[8:]
            else: raise OperationError, "invalid version, got '%s', expected 'live' or 'version/*'" % version

        self.perform(db, user, author_name, extension_name, version)
        return OperationResult()

class InstallExtension(ExtensionOperation):
    def __init__(self):
        ExtensionOperation.__init__(self, installExtension)

class UninstallExtension(ExtensionOperation):
    def __init__(self):
        ExtensionOperation.__init__(self, uninstallExtension)

class ReinstallExtension(ExtensionOperation):
    def __init__(self):
        ExtensionOperation.__init__(self, reinstallExtension)
