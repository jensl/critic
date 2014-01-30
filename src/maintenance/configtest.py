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

import contextlib
import traceback

def reflow(text, indent):
    try:
        import textutils
        return textutils.reflow(text, indent=indent)
    except Exception:
        # The 'textutils' module depends on 'configuration', so make our
        # dependency on it conditional.
        return text

class ConfigurationValue(object):
    def __init__(self, module, name):
        self.path = module.__file__
        if self.path.endswith(".pyc") or self.path.endswith(".pyo"):
            self.path = self.path[:-1]
        self.name = name

class ConfigurationIssue(object):
    def __init__(self, issue_type, message, values):
        self.type = issue_type
        self.message = message
        self.values = values[:]

    def __str__(self):
        result = self.type.upper() + "\n"
        if self.values:
            result += "  Relating to settings:\n"
            for value in self.values:
                result += "    %s :: %s\n" % (value.path, value.name)
        result += "  Message:\n"
        result += reflow(self.message, indent=4)
        return result

def doTestConfiguration():
    """Do not call directly; call testConfiguration()"""

    import configuration

    errors = []
    warnings = []
    values = []

    def error(message):
        errors.append(ConfigurationIssue("error", message, values))
    def warn(message):
        warnings.append(ConfigurationIssue("warning", message, values))

    class MissingValue(Exception):
        pass

    @contextlib.contextmanager
    def value(module, name):
        values.append(ConfigurationValue(module, name))
        if not hasattr(module, name):
            error("Configuration value missing: %s.%s" % (module.__name__, name))
            raise MissingValue
        yield getattr(module, name)
        del values[-1]

    def checkProvider(providers, name):
        provider = providers[name]
        if provider.get("enabled"):
            if not provider.get("client_id"):
                error("Enabled external authentication provider %r must have "
                      "'client_id' set." % name)
            if not provider.get("client_secret"):
                error("Enabled external authentication provider %r must have "
                      "'client_secret' set." % name)
            if name == "google" and not provider.get("redirect_uri"):
                error("Enabled external authentication provider %r must have "
                      "'redirect_uri' set." % name)
            if provider.get("bypass_createuser") \
                    and provider.get("verify_email_addresses"):
                error("Enabled external authentication provider %r can't have "
                      "both 'bypass_createuser' and 'verify_email_addresses' "
                      "enabled." % name)

    try:
        with value(configuration.base, "AUTHENTICATION_MODE") \
                as authentication_mode:
            if authentication_mode == "critic":
                with value(configuration.base, "SESSION_TYPE") as session_type:
                    if session_type not in ("httpauth", "cookie"):
                        error("Invalid session type: must be one of 'httpauth' "
                              "and 'cookie'.")
            elif authentication_mode == "host":
                with value(configuration.base, "ALLOW_ANONYMOUS_USER") \
                        as allow_anonymous_user:
                    if allow_anonymous_user:
                        warn("Allowing anonymous users is not possible when "
                             "the host web-server handles authentication.")
            else:
                # Unconditional external authentication mode
                with value(configuration.base, "SESSION_TYPE") as session_type:
                    if session_type != "cookie":
                        error("Invalid session type: must be 'cookie' (with "
                              "external authentication.)")
                with value(configuration.auth, "PROVIDERS") as providers:
                    if authentication_mode not in providers:
                        error("Authentication mode must be 'host', 'critic' or "
                              "name an external authentication provider.")
                    else:
                        provider = providers[authentication_mode]
                        if not provider.get("enabled"):
                            error("External authentication provider %r must be "
                                  "enabled." % authentication_mode)
                with value(configuration.base, "REPOSITORY_URL_TYPES") \
                        as repository_url_types:
                    if "http" in repository_url_types:
                        warn("HTTP/HTTPS repository URL type is incompatible "
                             "with using an external authentication provider.")
    except MissingValue:
        pass

    try:
        with value(configuration.auth, "PROVIDERS") as providers:
            for name in providers.keys():
                checkProvider(providers, name)
    except MissingValue:
        pass

    return (errors, warnings)

def testConfiguration():
    """Test the system configuration

       Returns a tuple containing two lists of ConfigurationIssue objects.  The
       first list contains errors, the second warnings.  If the first list is
       empty, the configuration should be usable."""

    try:
        return doTestConfiguration()
    except Exception:
        error = ConfigurationIssue(
            "error",
            "FATAL: Failed to test configuration!\n\n" + traceback.format_exc(),
            [])
        return ([error], [])
