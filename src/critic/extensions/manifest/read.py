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

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Type, TypeVar, cast
import yaml
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from critic import api

from .error import ManifestError
from .package import Package
from .pythonpackage import PythonPackage
from .role import Role
from .endpointrole import EndpointRole
from .filterhookrole import FilterHookRole
from .processcommitsrole import ProcessCommitsRole
from .uiaddonrole import UIAddonRole
from .subscriptionrole import SubscriptionRole


def valid_flavor(flavor_name: str) -> bool:
    flavor = getattr(api.critic.settings().extensions.flavors, flavor_name, None)
    if not flavor:
        logger.debug(
            "Invalid flavor: %s",
            flavor_name,
            api.critic.settings().extensions.flavors.items(),
        )
        return False
    return getattr(flavor, "enabled", False)


class Author:
    name: str
    email: Optional[str]

    def __init__(self, value: str):
        match = re.match(r"\s*(.*?)(?:\s+<([^>]+)>)?\s*$", value)
        if not match:
            raise ManifestError(f"Invalid author: {value!r}")
        self.name, self.email = match.groups()


@dataclass
class Setting:
    key: str
    description: str
    value: object
    privileged: bool


T = TypeVar("T")


class Accessor:
    data: Dict[str, object]

    def __init__(self, data: Any, context: str = ""):
        self.context = f"{context}: " if context else ""
        if not isinstance(data, dict):
            raise ManifestError(f"{self.context}not an object")
        self.data = data

    def get(
        self, name: str, value_type: Type[T], check_type: Optional[Type[object]] = None
    ) -> Optional[T]:
        try:
            value = self.data[name]
        except KeyError:
            return None
        if not (
            isinstance(value, value_type)
            if check_type is None
            else isinstance(value, check_type)  # type: ignore
        ):
            raise ManifestError(
                f"{self.context}invalid field value: {name}: "
                f"expected {value_type.__name__}"
            )
        return cast(Optional[T], value)

    def required(
        self, name: str, value_type: Type[T], check_type: Optional[Type[object]] = None
    ) -> T:
        value = self.get(name, value_type, check_type)
        if value is None:
            raise ManifestError(f"{self.context}missing required field: {name}")
        return value


class Manifest(object):
    name: str
    authors: List[Author]
    description: Optional[str]
    flavor: Optional[str]
    package: Optional[Package]
    roles: List[Role]
    settings: List[Setting]

    def __init__(
        self,
        *,
        filename: str,
        source: str,
        path: Optional[str] = None,
    ):
        self.filename = filename
        self.source = source
        if path:
            self.context = os.path.join(path, filename)
        else:
            self.context = filename
        self.authors = []
        self.description = None
        self.flavor = None
        self.package = None
        self.roles = []
        self.status = None
        self.hidden = False
        self.package = None
        self.settings = []

    def getAuthors(self):
        return self.authors

    def read(self) -> None:
        assert self.source is not None

        configuration = yaml.safe_load(self.source)

        accessor = Accessor(configuration)

        self.name = accessor.required("name", str)
        self.authors = [
            Author(author) for author in accessor.required("authors", List[str], list)
        ]
        self.description = accessor.required("description", str)

        if "package" in configuration:
            package_accessor = Accessor(configuration["package"], "package")

            package_type = package_accessor.required("type", str)

            if package_type not in Package.package_types:
                raise ManifestError(f"invalid package type: {package_type}")

            if package_type == "python":
                self.package = PythonPackage()

                entrypoints = package_accessor.get(
                    "entrypoints", Dict[str, object], dict
                )
                if entrypoints:
                    for name, entrypoint in entrypoints.items():
                        entrypoint_accessor = Accessor(
                            entrypoint, f"entrypoint `{name}`"
                        )
                        target = entrypoint_accessor.required("target", str)
                        self.package.add_entrypoint(name, target)

                dependencies = package_accessor.get("dependencies", List[str], list)
                if dependencies:
                    for dependency in dependencies:
                        self.package.add_dependency(dependency)

        def process_settings(prefix: str, settings: Dict[str, Any]) -> None:
            if all(isinstance(value, dict) for value in settings.values()):
                for key, value in settings.items():
                    process_settings(f"{prefix}{key}.", value)
            else:
                key = prefix.rstrip(".")
                settings_accessor = Accessor(settings, f"settings.{key}")
                description = settings_accessor.required("description", str)
                value = settings_accessor.get("value", object)
                privileged = settings_accessor.get("privileged", bool) or False
                self.settings.append(Setting(key, description, value, privileged))

        settings_configuration = configuration.get("settings")
        if settings_configuration:
            process_settings("", settings_configuration)

        default_flavor = configuration.get("flavor", "native")

        for index, role_configuration in enumerate(
            accessor.required("roles", List[object], list)
        ):
            role_accessor = Accessor(role_configuration, f"role {index + 1}")

            role_type = role_accessor.required("type", str)
            role: Role
            if role_type == "endpoint":
                role = EndpointRole(name=role_accessor.required("name", str))
            elif role_type == "processcommits":
                role = ProcessCommitsRole()
            elif role_type == "filterhook":
                role = FilterHookRole(
                    name=role_accessor.required("name", str),
                    title=role_accessor.required("title", str),
                    data_description=role_accessor.get("data_description", str),
                )
            elif role_type == "uiaddon":
                role = UIAddonRole(
                    name=role_accessor.required("name", str),
                    bundle_js=role_accessor.required("bundle_js", str),
                    bundle_css=role_accessor.get("bundle_css", str),
                )
            elif role_type == "subscription":
                role = SubscriptionRole(channel=role_accessor.required("channel", str))
            else:
                raise ManifestError(
                    "%s: invalid role type: %s" % (self.context, role_type)
                )

            if role.does_execute:
                flavor = role_accessor.get("flavor", str) or default_flavor
                if not valid_flavor(flavor):
                    raise ManifestError(
                        "%s: invalid (or disabled) flavor: %s" % (self.context, flavor)
                    )
                if flavor == "native":
                    assert self.package and self.package.package_type == "python"
                    role.set_execute(
                        flavor=flavor,
                        entrypoint=role_accessor.required("entrypoint", str),
                    )
                else:
                    raise ManifestError(
                        "%s: invalid role flavor: %s" % (self.context, flavor)
                    )

            role.set_description(role_accessor.required("description", str))

            self.roles.append(role)

        if not self.roles:
            raise ManifestError("%s: manifest error: no roles defined" % self.context)
