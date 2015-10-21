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

import extensions
import page.utils

def renderLoadManifest(req, db, user):
    key = req.getParameter("key")

    if "/" in key:
        author_name, extension_name = key.split("/", 1)
    else:
        author_name, extension_name = None, key

    def load():
        try:
            extension = extensions.extension.Extension(author_name, extension_name)
        except extensions.extension.ExtensionError as error:
            return str(error)

        try:
            extension.getManifest()
        except extensions.manifest.ManifestError as error:
            return str(error)

        return "That's a valid manifest, friend."

    return page.utils.ResponseBody(load(), content_type="text/plain")
