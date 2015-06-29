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

import sys
import os
import os.path
import re
import subprocess

import installation

this_module = sys.modules[__name__]

def find_executable(name):
    for search_path in os.environ["PATH"].split(":"):
        path = os.path.join(search_path, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None

headless = False

aptget = None
aptget_approved = False
aptget_updated = False

need_blankline = False

installed_packages = []

def blankline():
    global need_blankline
    if need_blankline:
        print
        need_blankline = False

def install_packages(*packages):
    global aptget, aptget_approved, aptget_updated, need_blankline, all_ok
    if aptget is None:
        aptget = find_executable("apt-get")
    if aptget and not aptget_approved:
        all_ok = False
        print """\
Found 'apt-get' executable in your $PATH.  This script can attempt to install
missing software using it.
"""
        aptget_approved = installation.input.yes_or_no(
            prompt="Do you want to use 'apt-get' to install missing packages?",
            default=True)
        if not aptget_approved: aptget = False
    if aptget:
        aptget_env = os.environ.copy()
        if headless:
            aptget_env["DEBIAN_FRONTEND"] = "noninteractive"
        if not aptget_updated:
            subprocess.check_output(
                [aptget, "-qq", "update"],
                env=aptget_env)
            aptget_updated = True
        aptget_output = subprocess.check_output(
            [aptget, "-qq", "-y", "install"] + list(packages),
            env=aptget_env)
        installed = {}
        for line in aptget_output.splitlines():
            match = re.match(r"^Setting up ([^ ]+) \(([^)]+)\) \.\.\.", line)
            if match:
                package_name, version = match.groups()
                if package_name in packages:
                    need_blankline = True
                    installed_packages.append((package_name, version))
                    installed[package_name] = version
                    print "Installed: %s (%s)" % (package_name, version)
        return installed
    else:
        return False

class Prerequisite(object):
    def __init__(self, name, packages, message):
        self.name = name
        self.packages = packages
        self.message = message

        setattr(this_module, name, self)

    def install(self):
        if self.check():
            return True
        if self.packages is None:
            print "ERROR: Installing '%s' is not supported!" % self.name
            return False
        if aptget_approved and install_packages(*self.packages):
            if self.check():
                return True
        blankline()
        print self.message
        print
        if not aptget_approved:
            install_packages(*self.packages)
        if self.check():
            return True
        print "ERROR: Installing '%s' failed!" % self.name
        return False

class Executable(Prerequisite):
    def __init__(self, name, packages, message):
        super(Executable, self).__init__(name, packages, message)
        self.path = None

    def check(self):
        if not self.path:
            self.path = find_executable(self.name)
        return bool(self.path)

    def install(self):
        if self.check():
            return True
        blankline()
        print "No '%s' executable found in $PATH" % self.name
        print
        return super(Executable, self).install()

class PythonLibrary(Prerequisite):
    def __init__(self, name, packages, message):
        super(PythonLibrary, self).__init__(name, packages, message)
        self.available = False

    def check(self):
        if not self.available:
            try:
                subprocess.check_output(
                    [sys.executable, "-c", "import " + self.name],
                    stderr=subprocess.STDOUT)
                self.available = True
            except subprocess.CalledProcessError:
                pass
        return self.available

    def install(self):
        if self.check():
            return True
        blankline()
        print "Failed to import '%s'" % self.name
        print
        return super(PythonLibrary, self).install()

class CustomCheck(Prerequisite):
    """Perform a custom check, and otherwise install packages"""

    def __init__(self, callback, name, packages, message):
        super(CustomCheck, self).__init__(name, packages, message)
        self.callback = callback
        self.available = False

    def check(self):
        if not self.available:
            if self.callback():
                self.available = True
        return self.available

    def install(self):
        if self.check():
            return True
        return super(CustomCheck, self).install()

def check_mod_wsgi():
    return os.path.isfile("/etc/apache2/mods-available/wsgi.load")

# This one is hardcoded to the running interpreter (rather than what we might
# find in the search path.)
Executable("python", None, None).path = sys.executable

prerequisites = [

    # We won't bother trying to install this; it won't be missing.
    Executable("tar", None, None),

    Executable("git", ["git-core"], """\
Make sure the Git version control system is installed.  Is Debian/Ubuntu the
package you need to install is 'git-core' (or 'git' in newer versions, but
'git-core' typically still works.)  The source code can be downloaded here:

  https://github.com/git/git"""),

    Executable("psql", ["postgresql", "postgresql-client"], """\
Make sure the PostgreSQL database server and its client utilities are installed.
In Debian/Ubuntu, the packages you need to install are 'postgresql' and
'postgresql-client'."""),

    PythonLibrary("psycopg2", ["python-psycopg2"], """\
Failed to import the 'psycopg2' module, which is used to access the PostgreSQL
database from Python.  In Debian/Ubuntu, the module is provided by the
'python-psycopg2' package.  The source code can be downloaded here:

  http://www.initd.org/psycopg/download/"""),

    PythonLibrary("requests", ["python-requests"], """\
Failed to import the 'requests' module, which is used to perform URL requests.
In Debian/Ubuntu, the module is provided by the 'python-requests' package.  The
source code can be downloaded here:

  https://github.com/kennethreitz/requests"""),

    PythonLibrary("pygments", ["python-pygments"], """\
Failed to import the 'pygments' module, which is used for syntax highlighting.
In Debian/Ubuntu, the module is provided by the 'python-pygments' package.  The
source code can be downloaded here:

  http://pygments.org/download/"""),

    Executable("apache2ctl", ["apache2", "libapache2-mod-wsgi"], """\
Make sure the Apache web server is installed.  In Debian/Ubuntu, the package you
need to install is 'apache2'.

In addition, the mod_wsgi Apache module needs to be installed.  In
Debian/Ubuntu, the package you need to install is 'libapache2-mod-wsgi'."""),

    # Additional executables that we use but that should have been installed
    # along with apache2ctl.
    Executable("a2enmod", None, None),
    Executable("a2ensite", None, None),
    Executable("a2dismod", None, None),
    Executable("a2dissite", None, None),

    # This extra check is really only needed if Apache was already installed
    # (and thus not installed by the prerequisite above).
    CustomCheck(check_mod_wsgi, "mod_wsgi", ["libapache2-mod-wsgi"], """\
The WSGI Apache module (mod_wsgi) doesn't appear to be installed.  Make sure
it's installed.  In Debian/Ubuntu, the package you need to install is
'libapache2-mod-wsgi'.  The source code can be downloaded here:

  http://code.google.com/p/modwsgi/wiki/DownloadTheSoftware?tm=2"""),

]

# The passlib library is only needed if Critic is configured to do
# authentication, so doesn't go into the list above yet.
passlib_library = PythonLibrary("passlib", ["python-passlib"], """\
Failed to import the 'passlib' module, which is required when Critic is
configured to handle user authentication itself.  In Debian/Ubuntu, the module
is provided by the 'python-passlib' package.  The source code can be downloaded
here:

  https://pypi.python.org/pypi/passlib""")

def resolve_prerequisites():
    if installation.config.auth_mode == "critic":
        prerequisites.append(passlib_library)

def prepare(mode, arguments, data):
    global headless
    headless = arguments.headless
    return True

def install(data):
    resolve_prerequisites()

    print """
Critic Installation: Prerequisites
==================================
"""

    if not all(prerequisite.install() for prerequisite in prerequisites):
        return False

    if installed_packages:
        blankline()
        print "Installed %d packages." % len(installed_packages)
        print
    else:
        print "All prerequisites available."

    data["installation.prereqs.python"] = python.path
    data["installation.prereqs.git"] = git.path
    data["installation.prereqs.tar"] = tar.path

    return True

def upgrade(arguments, data):
    import configuration

    python.path = configuration.executables.PYTHON
    git.path = configuration.executables.GIT
    tar.path = configuration.executables.TAR

    resolve_prerequisites()

    if not all(prerequisite.install() for prerequisite in prerequisites):
        return False

    data["installation.prereqs.python"] = python.path
    data["installation.prereqs.git"] = git.path
    data["installation.prereqs.tar"] = tar.path

    return True
