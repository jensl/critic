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

import functools
import logging
import os
import re
from typing import Any, Dict, List, Optional
import yaml
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from critic import api

from . import ManifestError, MANIFEST_FILENAMES
from .package import Package
from .pythonpackage import PythonPackage
from .role import Role
from .endpointrole import EndpointRole
from .filterhookrole import FilterHookRole
from .processcommitsrole import ProcessCommitsRole
from .uiaddonrole import UIAddonRole
from .subscriptionrole import SubscriptionRole


def valid_flavor(flavor_name):
    flavor = getattr(api.critic.settings().extensions.flavors, flavor_name, None)
    if not flavor:
        logger.debug(
            "Invalid flavor: %s",
            flavor_name,
            api.critic.settings().extensions.flavors.items(),
        )
        return False
    return getattr(flavor, "enabled", False)


class Author(object):
    def __init__(self, value):
        match = re.match(r"\s*(.*?)\s+<(.+?)>\s*$", value)
        if match:
            self.name, self.email = match.groups()
        else:
            self.name = value.strip()
            self.email = None


@dataclass
class Setting:
    key: str
    description: str
    value: object
    privileged: bool


class Manifest(object):
    authors: List[Author]
    flavor: Optional[str]
    package: Optional[Package]
    roles: List[Role]
    settings: List[Setting]

    def __init__(self, *, path: str = None, filename: str = None, source: str = None):
        self.path = path
        self.filename = filename
        self.source = source
        self.authors = []
        self.description = None
        self.flavor = None
        self.package = None
        self.roles = []
        self.status = None
        self.hidden = False
        self.package = None
        self.settings = []

    def isAuthor(self, db, user):
        for author in self.authors:
            if author.name in (user.name, user.fullname) or user.hasGitEmail(
                db, author.email
            ):
                return True
        return False

    def getAuthors(self):
        return self.authors

    def read(self):
        configuration = yaml.safe_load(self.source)

        def configuration_field(context, configuration, required, name, field_type=str):
            try:
                value = configuration[name]
            except KeyError:
                if not required:
                    return None
                if context:
                    context += ": "
                raise ManifestError(f"{context}missing required field: {name}")
            if not isinstance(value, field_type):
                raise ManifestError(
                    f"{context}invalid field value: {name}: "
                    f"expected {field_type.__name__}"
                )
            return value

        required_field = functools.partial(configuration_field, "", configuration, True)

        self.authors = [Author(author) for author in required_field("authors", list)]
        self.description = required_field("description")

        package_configuration = configuration.get("package")
        if package_configuration:
            package_field = functools.partial(
                configuration_field, "package", package_configuration
            )

            package_type = package_field(True, "type")

            if package_type not in Package.package_types:
                raise ManifestError(f"invalid package type: {package_type}")

            if package_type == "python":
                self.package = PythonPackage()

                entrypoints = package_field(False, "entrypoints", dict)
                if entrypoints:
                    for name in entrypoints:
                        target = configuration_field(
                            f"entrypoint `{name}`", entrypoints, True, name
                        )
                        self.package.add_entrypoint(name, target)

                dependencies = package_field(False, "dependencies", list)
                if dependencies:
                    for dependency in dependencies:
                        self.package.add_dependency(dependency)

        def process_settings(prefix: str, settings: Dict[str, Any]) -> None:
            if all(isinstance(value, dict) for value in settings.values()):
                for key, value in settings.items():
                    process_settings(f"{prefix}{key}.", value)
            else:
                key = prefix.rstrip(".")
                description = configuration_field(
                    f"settings.{key}", settings, True, "description"
                )
                value = settings.get("value", None)
                privileged = settings.get("privileged", False)
                self.settings.append(Setting(key, description, value, privileged))

        settings_configuration = configuration.get("settings")
        if settings_configuration:
            process_settings("", settings_configuration)

        default_flavor = configuration.get("flavor", "native")

        for index, role_configuration in enumerate(required_field("roles", list)):
            required_role_field = functools.partial(
                configuration_field, f"role {index + 1}", role_configuration, True
            )

            role_type = required_role_field("type")
            if role_type == "endpoint":
                role = EndpointRole(name=required_role_field("name"))
            elif role_type == "processcommits":
                role = ProcessCommitsRole()
            elif role_type == "filterhook":
                role = FilterHookRole(
                    name=required_role_field("name"),
                    title=required_role_field("title"),
                    data_description=role_configuration.get("data_description"),
                )
            elif role_type == "uiaddon":
                role = UIAddonRole(
                    name=required_role_field("name"),
                    bundle_js=required_role_field("bundle_js"),
                    bundle_css=role_configuration.get("bundle_css"),
                )
            elif role_type == "subscription":
                role = SubscriptionRole(channel=required_role_field("channel"))
            else:
                raise ManifestError(
                    "%s: invalid role type: %s" % (self.path, role_type)
                )

            if role.does_execute:
                flavor = role_configuration.get("flavor", default_flavor)
                if not valid_flavor(flavor):
                    raise ManifestError(
                        "%s: invalid (or disabled) flavor: %s" % (self.path, flavor)
                    )
                if flavor == "native":
                    assert self.package.package_type == "python"
                    role.set_execute(
                        flavor=flavor, entrypoint=required_role_field("entrypoint")
                    )
                else:
                    raise ManifestError(
                        "%s: invalid role flavor: %s" % (self.path, flavor)
                    )

            role.set_description(required_role_field("description"))
            role.check(self)

            self.roles.append(role)

        if not self.roles:
            raise ManifestError("%s: manifest error: no roles defined" % self.path)

    @staticmethod
    def load(extension_path):
        manifest = Manifest(extension_path)
        manifest.read()
        return manifest
