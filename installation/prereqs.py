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

def find_executable(name):
    for search_path in os.environ["PATH"].split(":"):
        path = os.path.join(search_path, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

python = sys.executable
git = None
tar = None
psql = None
apache2ctl = None
a2enmod = None
a2ensite = None
a2dissite = None

psycopg2_available = False
pygments_available = False
passlib_available = False
requests_available = False

aptget = None
aptget_approved = False
aptget_updated = False

need_blankline = False

def blankline():
    global need_blankline
    if need_blankline:
        print
        need_blankline = False

def install_packages(arguments, *packages):
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
        if arguments.headless:
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
                    installed[package_name] = version
                    print "Installed: %s (%s)" % (package_name, version)
        return installed
    else:
        return False

def check(mode, arguments):
    global git, tar, psql, passlib_available, apache2ctl, a2enmod, a2ensite, a2dissite

    if mode == "install":
        print """
Critic Installation: Prerequisites
==================================
"""

    success = True
    all_ok = True

    git = find_executable("git")
    if not git:
        if aptget_approved and install_packages(arguments, "git-core"):
            git = find_executable("git")
        if not git:
            blankline()
            all_ok = False
            print """\
No 'git' executable found in $PATH.  Make sure the Git version control system
is installed.  Is Debian/Ubuntu the package you need to install is 'git-core'
(or 'git' in newer versions, but 'git-core' typically still works.)  The source
code can be downloaded here:

  https://github.com/git/git
"""
            if not aptget_approved and install_packages(arguments, "git-core"):
                git = find_executable("git")
            if not git: success = False

    tar = find_executable("tar")
    assert tar, "System has no 'tar'?!?"

    psql = find_executable("psql")
    if not psql:
        if aptget_approved and install_packages(arguments, "postgresql", "postgresql-client"):
            psql = find_executable("psql")
        if not psql:
            blankline()
            all_ok = False
            print """\
No 'psql' executable found in $PATH.  Make sure the PostgreSQL database server
and its client utilities are installed.  In Debian/Ubuntu, the packages you need
to install are 'postgresql' and 'postgresql-client'.
"""
            if not aptget_approved and install_packages(arguments, "postgresql", "postgresql-client"):
                psql = find_executable("psql")
            if not psql: success = False

    if psql:
        postgresql_version = subprocess.check_output([psql, "--version"]).splitlines()[0].split()[-1].split(".")

        postgresql_major = postgresql_version[0]
        postgresql_minor = postgresql_version[1]

        if postgresql_major < 9 or (postgresql_major == 9 and postgresql_minor < 1):
            blankline()
            all_ok = False
            print """\
Unsupported PostgreSQL version!  Critic requires PostgreSQL 9.1.x or later.
"""
            sys.exit(1)

    apache2ctl = find_executable("apache2ctl")
    if not apache2ctl:
        if aptget_approved and install_packages(arguments, "apache2"):
            apache2ctl = find_executable("apache2ctl")
        if not apache2ctl:
            blankline()
            all_ok = False
            print """\
No 'apache2ctl' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install_packages(arguments, "apache2"):
                apache2ctl = find_executable("apache2ctl")
            if not apache2ctl: success = False

    a2enmod = find_executable("a2enmod")
    if not a2enmod:
        if aptget_approved and install_packages(arguments, "apache2"):
            a2enmod = find_executable("a2enmod")
        if not a2enmod:
            blankline()
            all_ok = False
            print """\
No 'a2enmod' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install_packages(arguments, "apache2"):
                a2enmod = find_executable("a2enmod")
            if not a2enmod: success = False

    a2ensite = find_executable("a2ensite")
    if not a2ensite:
        if aptget_approved and install_packages(arguments, "apache2"):
            a2ensite = find_executable("a2ensite")
        if not a2ensite:
            blankline()
            all_ok = False
            print """\
No 'a2ensite' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install_packages(arguments, "apache2"):
                a2ensite = find_executable("a2ensite")
            if not a2ensite: success = False

    a2dissite = find_executable("a2dissite")
    if not a2dissite:
        if aptget_approved and install_packages(arguments, "apache2"):
            a2dissite = find_executable("a2dissite")
        if not a2dissite:
            blankline()
            all_ok = False
            print """\
No 'a2dissite' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install_packages(arguments, "apache2"):
                a2dissite = find_executable("a2dissite")
            if not a2dissite: success = False

    if not os.path.isdir(os.path.join("/etc", "apache2", "mods-available")):
        print """\
There's no /etc/apache2/mods-available/ directory.  This means I don't know how
to determine whether the 'wsgi' Apache module is available, and will just have
to assume it is.  If you know it *isn't* available, you should install it, or
abort this script now.
"""
        abort = installation.input.yes_or_no(
            prompt="Do you want to abort this script now?",
            default=False)
        if abort: sys.exit(1)
        else: mod_wsgi_available = True
    else:
        mod_wsgi_available_path = os.path.join("/etc", "apache2", "mods-available", "wsgi.load")
        mod_wsgi_available = os.path.isfile(mod_wsgi_available_path)
        if not mod_wsgi_available:
            if aptget_approved and install_packages(arguments, "libapache2-mod-wsgi"):
                mod_wsgi_available = os.path.isfile(mod_wsgi_available_path)
            if not mod_wsgi_available:
                blankline()
                all_ok = False
                print """\
The WSGI Apache module (mod_wsgi) doesn't appear to be installed.  Make sure
it's installed.  In Debian/Ubuntu, the package you need to install is
'libapache2-mod-wsgi'.  The source code can be downloaded here:

  http://code.google.com/p/modwsgi/wiki/DownloadTheSoftware?tm=2
"""
                if not aptget_approved and install_packages(arguments, "libapache2-mod-wsgi"):
                    mod_wsgi_available = os.path.isfile(mod_wsgi_available_path)
                if not mod_wsgi_available: success = False

    def check_psycopg2():
        global psycopg2_available
        try:
            import psycopg2
            psycopg2_available = True
        except ImportError: pass

    check_psycopg2()
    if not psycopg2_available:
        if aptget_approved and install_packages(arguments, "python-psycopg2"):
            check_psycopg2()
        if not psycopg2_available:
            blankline()
            all_ok = False
            print """\
Failed to import the 'psycopg2' module, which is used to access the PostgreSQL
database from Python.  In Debian/Ubuntu, the module is provided by the
'python-psycopg2' package.  The source code can be downloaded here:

  http://www.initd.org/psycopg/download/
"""
        if not aptget_approved and install_packages(arguments, "python-psycopg2"):
            check_psycopg2()
        if not psycopg2_available:
            success = False

    def check_pygments():
        global pygments_available
        try:
            import pygments
            pygments_available = True
        except ImportError: pass

    check_pygments()
    if not pygments_available:
        if aptget_approved and install_packages(arguments, "python-pygments"):
            check_pygments()
        if not pygments_available:
            blankline()
            all_ok = False
            print """\
Failed to import the 'pygments' module, which is used for syntax highlighting.
In Debian/Ubuntu, the module is provided by the 'python-pygments' package.  The
source code can be downloaded here:

  http://pygments.org/download/
"""
        if not aptget_approved and install_packages(arguments, "python-pygments"):
            check_pygments()
        if not pygments_available:
            success = False

    def check_passlib():
        global passlib_available
        try:
            subprocess.check_output(
                [sys.executable, "-c", "import passlib"],
                stderr=subprocess.STDOUT)
            passlib_available = True
        except subprocess.CalledProcessError:
            pass

    global passlib_available

    check_passlib()
    if not passlib_available:
        if mode == "install":
            auth_mode = arguments.auth_mode
        else:
            import configuration
            auth_mode = configuration.base.AUTHENTICATION_MODE

        if auth_mode == "critic":
            install_passlib = True
        else:
            blankline()
            all_ok = False
            print """\
Failed to import the 'passlib' module, which is required if you want Critic to
handle user authentication itself.  If user authentication is to be handled by
Apache instead there is no need to install the passlib module.

In Debian/Ubuntu, the module is provided by the 'python-passlib' package.  The
source code can be downloaded here:

  https://pypi.python.org/pypi/passlib
"""
            install_passlib = installation.input.yes_or_no(
                "Do you want to install the 'passlib' module?",
                default=False)
        if install_passlib:
            if install_packages(arguments, "python-passlib"):
                check_passlib()
                if not passlib_available:
                    print """
Failed to import 'passlib' module!  Installing it appeared to go fine, though,
so you might just need to restart this script."""
        if install_passlib and not passlib_available:
            success = False

    def check_requests():
        global requests_available
        try:
            import requests
            requests_available = True
        except ImportError: pass

    check_requests()
    if not requests_available:
        if aptget_approved and install_packages(arguments, "python-requests"):
            check_requests()
        if not requests_available:
            blankline()
            all_ok = False
            print """\
Failed to import the 'requests' module, which is used to perform URL requests.
In Debian/Ubuntu, the module is provided by the 'python-requests' package.  The
source code can be downloaded here:

  https://github.com/kennethreitz/requests
"""
        if not aptget_approved and install_packages(arguments, "python-requests"):
            check_requests()
        if not requests_available:
            success = False

    if mode == "install" and all_ok:
        print "All prerequisites available."

    return success

def prepare(mode, arguments, data):
    if mode == "install":
        data["installation.prereqs.python"] = python
        data["installation.prereqs.git"] = git
        data["installation.prereqs.tar"] = tar
    else:
        import configuration

        data["installation.prereqs.python"] = configuration.executables.PYTHON
        data["installation.prereqs.git"] = configuration.executables.GIT
        data["installation.prereqs.tar"] = configuration.executables.TAR

    return True
