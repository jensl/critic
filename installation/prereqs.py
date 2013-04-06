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

import installation
from installation import process

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
bcrypt_available = False

aptget = None
aptget_approved = False

need_blankline = False

def blankline():
    global need_blankline
    if need_blankline:
        print
        need_blankline = False

def check(arguments):
    global git, tar, psql, bcrypt_available, aptget, apache2ctl, a2enmod, a2ensite, a2dissite

    print """
Critic Installation: Prerequisites
==================================
"""

    success = True
    all_ok = True

    aptget = find_executable("apt-get")

    def install(*packages):
        global aptget, aptget_approved, need_blankline, all_ok
        if aptget and not aptget_approved:
            all_ok = False
            print """\
Found 'apt-get' executable in your $PATH.  This script can attempt to install
missing software using it.
"""
            aptget_approved = installation.input.yes_or_no(
                prompt="Do you want to use 'apt-get' to install missing packages?",
                default=True)
            if not aptget_approved: aptget = None
        if aptget:
            installed_anything = False
            aptget_env = os.environ.copy()
            if arguments.headless:
                aptget_env["DEBIAN_FRONTEND"] = "noninteractive"
            aptget_output = process.check_output(
                [aptget, "-qq", "-y", "install"] + list(packages),
                env=aptget_env)
            for line in aptget_output.splitlines():
                match = re.search(r"([^ ]+) \(.* \.\.\./([^)]+\.deb)\) \.\.\.", line)
                if match:
                    need_blankline = True
                    installed_anything = True
                    print "Installed: %s (%s)" % (match.group(1), match.group(2))
            return installed_anything
        else:
            return False

    git = find_executable("git")
    if not git:
        if aptget_approved and install("git-core"):
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
            if not aptget_approved and install("git-core"):
                git = find_executable("git")
            if not git: success = False

    tar = find_executable("tar")
    assert tar, "System has no 'tar'?!?"

    psql = find_executable("psql")
    if not psql:
        if aptget_approved and install("postgresql", "postgresql-client"):
            psql = find_executable("psql")
        if not psql:
            blankline()
            all_ok = False
            print """\
No 'psql' executable found in $PATH.  Make sure the PostgreSQL database server
and its client utilities are installed.  In Debian/Ubuntu, the packages you need
to install are 'postgresql' and 'postgresql-client'.
"""
            if not aptget_approved and install("postgresql", "postgresql-client"):
                psql = find_executable("psql")
            if not psql: success = False

    if psql:
        postgresql_version = process.check_output([psql, "--version"]).splitlines()[0].split()[-1].split(".")

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
        if aptget_approved and install("apache2"):
            apache2ctl = find_executable("apache2ctl")
        if not apache2ctl:
            blankline()
            all_ok = False
            print """\
No 'apache2ctl' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install("apache2"):
                apache2ctl = find_executable("apache2ctl")
            if not apache2ctl: success = False

    a2enmod = find_executable("a2enmod")
    if not a2enmod:
        if aptget_approved and install("apache2"):
            a2enmod = find_executable("a2enmod")
        if not a2enmod:
            blankline()
            all_ok = False
            print """\
No 'a2enmod' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install("apache2"):
                a2enmod = find_executable("a2enmod")
            if not a2enmod: success = False

    a2ensite = find_executable("a2ensite")
    if not a2ensite:
        if aptget_approved and install("apache2"):
            a2ensite = find_executable("a2ensite")
        if not a2ensite:
            blankline()
            all_ok = False
            print """\
No 'a2ensite' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install("apache2"):
                a2ensite = find_executable("a2ensite")
            if not a2ensite: success = False

    a2dissite = find_executable("a2dissite")
    if not a2dissite:
        if aptget_approved and install("apache2"):
            a2dissite = find_executable("a2dissite")
        if not a2dissite:
            blankline()
            all_ok = False
            print """\
No 'a2dissite' executable found in $PATH.  Make sure the Apache web server is
installed.  In Debian/Ubuntu, the package you need to install is 'apache2'.
"""
            if not aptget_approved and install("apache2"):
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
            if aptget_approved and install("libapache2-mod-wsgi"):
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
                if not aptget_approved and install("libapache2-mod-wsgi"):
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
        if aptget_approved and install("python-psycopg2"):
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
        if not aptget_approved and install("python-psycopg2"):
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
        if aptget_approved and install("python-pygments"):
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
        if not aptget_approved and install("python-pygments"):
            check_pygments()
        if not pygments_available:
            success = False

    def check_bcrypt():
        global bcrypt_available
        try:
            import bcrypt
            bcrypt_available = True
        except ImportError: pass

    global bcrypt_available

    check_bcrypt()
    if not bcrypt_available:
        if arguments.auth_mode == "critic":
            install_bcrypt = True
        else:
            blankline()
            all_ok = False
            print """\
Failed to import the 'bcrypt' module, which is required if you want Critic to
handle user authentication itself.  If user authentication is to be handled by
Apache instead there is no need to install the bcrypt module.

In Debian/Ubuntu, the module is provided by the 'python-bcrypt' package.  The
source code can be downloaded here:

  http://code.google.com/p/py-bcrypt/
"""
            install_bcrypt = installation.input.yes_or_no(
                "Do you want to install the 'bcrypt' module?",
                default=False)
        if install_bcrypt:
            if install("python-bcrypt"):
                check_bcrypt()
                if not bcrypt_available:
                    print """
Failed to import 'bcrypt' module!  Installing it appeared to go fine, though,
so you might just need to restart this script."""
        if install_bcrypt and not bcrypt_available:
            success = False

    if all_ok: print "All okay."

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
