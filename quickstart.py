# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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
import argparse
import tempfile
import shutil
import wsgiref.simple_server
import subprocess
import threading
import requests
import json
import signal
import time
import py_compile
import contextlib

sys.path.insert(0, os.path.dirname(__file__))

parser = argparse.ArgumentParser("python quickstart.py",
                                 description="Critic instance quick-start utility script.")
parser.add_argument("--quiet", action="store_true",
                    help="Suppress most output")
parser.add_argument("--testing", action="store_true",
                    help=argparse.SUPPRESS)

parser.add_argument("--admin-username", default=os.getlogin(),
                    help=argparse.SUPPRESS)
parser.add_argument("--admin-fullname", default=os.getlogin(),
                    help=argparse.SUPPRESS)
parser.add_argument("--admin-email", default=os.getlogin() + "@localhost",
                    help=argparse.SUPPRESS)
parser.add_argument("--admin-password", default="1234",
                    help=argparse.SUPPRESS)
parser.add_argument("--system-recipient", action="append",
                    help=argparse.SUPPRESS)

parser.add_argument("--state-dir", "-s",
                    help="State directory [default=temporary dir]")
parser.add_argument("--http-host", default="",
                    help="Hostname the HTTP server listens at [default=ANY]")
parser.add_argument("--http-port", "-p", default=8080, type=int,
                    help="Port the HTTP server listens at [default=8080]")

parser.add_argument("--smtp-host", default="localhost",
                    help="Hostname of SMTP server to use [default=localhost]")
parser.add_argument("--smtp-port", default=25, type=int,
                    help="Port of SMTP server to use [default=25]")
parser.add_argument("--smtp-username",
                    help="SMTP username [default=none]")
parser.add_argument("--smtp-password",
                    help="SMTP password [default=none]")

parser.add_argument("--run", action="store_true",
                    help=argparse.SUPPRESS)
parser.add_argument("--run-state-dir",
                    help=argparse.SUPPRESS)
parser.add_argument("--run-http-port", type=int,
                    help=argparse.SUPPRESS)

arguments = parser.parse_args()

quiet = arguments.quiet or arguments.testing

if arguments.run:
    import critic

    def handle_interrupt(signum, frame):
        pid_filename = os.path.join(arguments.run_state_dir, "run",
                                    "main", "servicemanager.pid")

        if os.path.isfile(pid_filename):
            with open(pid_filename) as pid_file:
                servicemanager_pid = int(pid_file.read().strip())

            os.kill(servicemanager_pid, signal.SIGTERM)

            while os.path.isfile(pid_filename):
                time.sleep(0.1)

        os._exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)

    subprocess.check_call([sys.executable, "-m", "background.servicemanager"])

    class CriticWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
        def log_message(self, *args, **kwargs):
            if not quiet:
                wsgiref.simple_server.WSGIRequestHandler.log_message(
                    self, *args, **kwargs)

    server = wsgiref.simple_server.make_server(
        host=arguments.http_host,
        port=arguments.run_http_port,
        app=critic.main,
        handler_class=CriticWSGIRequestHandler)

    server_address_path = os.path.join(arguments.run_state_dir, "server_address")

    with open(server_address_path, "w") as server_address_file:
        server_address_file.write("%s:%d" % (server.server_name, server.server_port))

    # This call will never return.  This is fine; we just want to block
    # forever (or until we receive a SIGINT.)
    server.serve_forever()

failed_imports = False

try:
    import pygments
except ImportError:
    print """\
ERROR: Failed to import 'pygments'; code will not be syntax highlighted.
HINT: On Debian/Ubuntu, install the 'python-pygments' package to eliminate
      this problem.
"""
    failed_imports = True

try:
    import passlib
except ImportError:
    print """\
ERROR: Failed to import 'passlib'; passwords will be encrypted insecurely.
HINT: On Debian/Ubuntu, install the 'python-passlib' package to eliminate
      this problem.
"""
    failed_imports = True

if failed_imports:
    if arguments.testing:
        print "FATAL: Won't run test suite with missing imports."
        sys.exit(1)
    else:
        print """\
Some functionality will be missing due to missing Python packages.  Press
ENTER to go ahead and quick-start Critic anyway, or CTRL-c to abort.
"""

        try:
            sys.stdin.readline()
        except KeyboardInterrupt:
            sys.exit(1)

if arguments.testing:
    os.setsid()

import installation
import installation.qs

installation.quiet = True

if arguments.state_dir:
    state_dir = arguments.state_dir
    if not os.path.isdir(state_dir):
        os.makedirs(state_dir)
else:
    state_dir = tempfile.mkdtemp()
    if arguments.testing:
        print "STATE=%s" % state_dir

database_path = os.path.join(state_dir, "critic.db")
initialize_database = not os.path.exists(database_path)
add_repository = None

class CompilationFailed(Exception):
    pass

def compile_all_sources():
    success = True
    for dirname, _, filenames in os.walk("src"):
        for filename in filenames:
            if filename[0] == ".":
                continue
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirname, filename)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as error:
                if success:
                    # First error.  Create some space.
                    print "\n"
                print "ERROR: Failed to compile %s:\n%s" % (path, error)
                success = False
    if not success:
        raise CompilationFailed()

@contextlib.contextmanager
def activity(what):
    if quiet:
        yield
    else:
        sys.stdout.write(what + " ...")
        sys.stdout.flush()
        yield
        sys.stdout.write(" done.\n")

try:
    try:
        with activity("Compiling all sources"):
            compile_all_sources()
    except CompilationFailed:
        sys.exit(1)

    installation.is_quick_start = True

    if initialize_database:
        with activity("Initializing database"):
            installation.qs.sqlite.import_schema(
                database_path,
                filenames=installation.database.SCHEMA_FILES,
                quiet=quiet)

    installation.system.uid = os.getuid()
    installation.system.gid = os.getgid()

    installation.paths.etc_dir = os.path.join(state_dir, "etc")
    installation.paths.bin_dir = os.path.join(state_dir, "bin")
    installation.paths.install_dir = os.path.join(os.getcwd(), "src")
    installation.paths.data_dir = os.path.join(state_dir, "data")
    installation.paths.cache_dir = os.path.join(state_dir, "cache")
    installation.paths.log_dir = os.path.join(state_dir, "log")
    installation.paths.run_dir = os.path.join(state_dir, "run")
    installation.paths.git_dir = os.path.join(state_dir, "git")

    data = installation.qs.data.generate(arguments, database_path)

    with activity("Installing the system"):
        installation.paths.install(data)

        if not os.path.isfile(os.path.join(installation.paths.bin_dir, "criticctl")):
            installation.criticctl.install(data)

        if not os.path.isfile(os.path.join(installation.paths.etc_dir, "main", "configuration", "__init__.py")):
            installation.config.install(data)

        if initialize_database:
            installation.prefs.install(data)

    config_dir = os.path.join(installation.paths.etc_dir, "main")
    install_dir = installation.paths.install_dir
    root_dir = installation.root_dir

    sys.path.insert(0, config_dir)
    sys.path.insert(1, install_dir)

    if initialize_database:
        import dbutils
        import auth

        db = dbutils.Database()
        db.cursor().execute("""INSERT INTO systemidentities (key, name, anonymous_scheme,
                                                             authenticated_scheme, hostname,
                                                             description, installed_sha1)
                                    VALUES ('main', 'main', 'http', 'http', 'localhost', 'Main', ?)""",
                            (subprocess.check_output("git rev-parse HEAD", shell=True).strip(),))

        admin = dbutils.User.create(
            db,
            name=arguments.admin_username,
            fullname=arguments.admin_fullname,
            email=arguments.admin_email,
            email_verified=None,
            password=auth.hashPassword(arguments.admin_password))

        if not arguments.testing:
            if not quiet:
                print

            print ("Created administrator user %r with password '1234'"
                   % data["installation.admin.username"])

        db.cursor().execute("""INSERT INTO userroles (uid, role)
                                    SELECT %s, name
                                      FROM roles""",
                            (admin.id,))

        db.commit()
        db.close()

    the_system = None
    server_address = None
    server_name = None
    server_port = str(arguments.http_port)

    def startTheSystem():
        global the_system, server_name, server_port, server_address

        server_address_path = os.path.join(state_dir, "server_address")
        if os.path.isfile(server_address_path):
            os.unlink(server_address_path)

        the_system = subprocess.Popen(
            [sys.executable] + sys.argv + ["--run",
                                           "--run-state-dir", state_dir,
                                           "--run-http-port", server_port],
            env={ "PYTHONPATH": ":".join([config_dir, install_dir, root_dir]) })

        while not os.path.isfile(server_address_path):
            time.sleep(0.1)

            if the_system.poll() is not None:
                the_system = None
                return False

        with open(server_address_path) as server_address_file:
            server_address = server_address_file.read()

        server_name, _, server_port = server_address.partition(":")
        return True

    def stopTheSystem():
        global the_system

        if the_system:
            the_system.send_signal(signal.SIGINT)
            the_system.wait()

        the_system = None

    def restartTheSystem():
        compile_all_sources()
        stopTheSystem()
        startTheSystem()

    def getNewestModificationTime():
        newest = 0
        for dirpath, dirnames, filenames in os.walk("."):
            for filename in filenames:
                if filename[0] != "." and filename.endswith(".py"):
                    path = os.path.join(dirpath, filename)
                    newest = max(os.stat(path).st_mtime, newest)
        return newest

    running_mtime = getNewestModificationTime()

    startTheSystem()

    if not arguments.testing:
        print "Listening at: http://%s:%s/" % (server_name, server_port)

        import dbutils

        db = dbutils.Database()
        db.cursor().execute("""UPDATE systemidentities
                                  SET hostname=?""",
                            ("%s:%s" % (server_name, server_port),))
        db.commit()
        db.close()
    else:
        print "HTTP=%s:%s" % (server_name, server_port)

    if not os.listdir(installation.paths.git_dir) and not arguments.testing:
        if not quiet:
            print
            print "Creating critic.git repository ..."

        pid_filename = os.path.join(
            state_dir, "run", "main", "branchtracker.pid")

        while not os.path.isfile(pid_filename):
            time.sleep(0.1)

        current_ref = subprocess.check_output(
            ["git", "rev-parse", "--symbolic-full-name", "HEAD"]).strip()

        if current_ref.startswith("refs/heads/"):
            remote_branch = local_branch = current_ref[len("refs/heads/"):]
            if local_branch.startswith("r/"):
                local_branch = local_branch[2:]
        else:
            remote_branch = local_branch = "master"

        session = requests.Session()
        response = session.post(
            "http://%s/validatelogin" % server_address,
            data=json.dumps({ "username": data["installation.admin.username"],
                              "password": "1234" }))
        if response.json().get("status") != "ok":
            print repr(response.json())
        response = session.post(
            "http://%s/addrepository" % server_address,
            data=json.dumps({ "name": "critic",
                              "path": "critic",
                              "mirror": { "remote_url": "file://" + installation.root_dir,
                                          "remote_branch": remote_branch,
                                          "local_branch": local_branch }}))
        if response.json().get("status") != "ok":
            print repr(response.json())

    if not quiet:
        print

    if arguments.testing:
        print "STARTED"

    if arguments.testing:
        time.sleep(3600)
    else:
        while True:
            current_mtime = getNewestModificationTime()
            if current_mtime > running_mtime:
                print
                try:
                    with activity("Sources changed, restarting the system"):
                        restartTheSystem()
                except CompilationFailed:
                    pass
                else:
                    print

                running_mtime = current_mtime
            else:
                time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    if not arguments.quiet and not arguments.testing:
        print "Shutting down ..."

    try:
        stopTheSystem()
    except NameError:
        # Failure happened before stopTheSystem() was declared.
        pass

    if not arguments.state_dir:
        if not arguments.quiet and not arguments.testing:
            print "Cleaing up ..."

        shutil.rmtree(state_dir)
