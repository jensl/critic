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

import os
import re
import subprocess
import time

import installation

arguments = None
instance = None

created_file = []
renamed = []

def backup_path(path):
    return os.path.join(os.path.dirname(path), "_" + os.path.basename(path))

def undoable_remove(path):
    os.rename(path, backup_path(path))
    renamed.append((path, backup_path(path)))

def process_configuration_file(
        mode, data, template_path, target_path, message=None):
    global created_file, renamed

    with open(template_path, "r") as template_file:
        template = template_file.read().decode("utf-8")
        source = template % data

    if mode == "install":
        write_target = True
    else:
        with open(target_path, "r") as target_file:
            target = target_file.read().decode("utf-8")

        if source != target:
            def generateVersion(label, path):
                if label == "updated":
                    with open(path, "w") as target:
                        target.write(source.encode("utf-8"))

            update_query = installation.utils.UpdateModifiedFile(
                arguments,
                message=message,
                versions={ "current": target_path,
                           "updated": target_path + ".new" },
                options=[ ("i", "install the updated version"),
                          ("k", "keep the current version"),
                          ("d", ("current", "updated")) ],
                generateVersion=generateVersion)

            write_target = update_query.prompt() == "i"
        else:
            write_target = False

        if write_target:
            if not getattr(arguments, "dry_run", False):
                undoable_remove(target_path)

            print "Updated file: %s" % target_path

    if write_target and not getattr(arguments, "dry_run", False):
        with open(target_path, "w") as target_file:
            created_file.append(target_path)
            os.chmod(target_path, 0640)
            target_file.write(source.encode("utf-8"))

class Service(object):
    def __init__(self):
        self.stopped = False

    def service_command(self, command, errors_are_fatal):
        print
        try:
            subprocess.check_call(["service", self.service_name, command])
        except subprocess.CalledProcessError:
            print "WARNING: The %s service failed to %s." % (self.display_name,
                                                             command)

            if errors_are_fatal:
                print """
You can now either abort this Critic installation/upgrade, or you can
go ahead anyway, fix the configuration problem manually (now or
later), and then make sure the %(name)s service is running yourself
using the command

  service %(name)s (start|restart)

Note that if you don't abort, the Critic system will most likely not
be accessible until the configuration problem has been fixed.
""" % { "name": self.service_name }
                return not installation.input.yes_or_no(
                    "Do you want to abort this Critic installation/upgrade?")
        return True

    def start(self, errors_are_fatal=True):
        print
        if not self.service_command("start", errors_are_fatal):
            return False
        self.stopped = False
        return True

    def stop(self, errors_are_fatal=False):
        print
        if not self.service_command("stop", errors_are_fatal):
            return False
        self.stopped = True
        return True

    def restart(self):
        print
        if not self.stop():
            return False
        return self.start()

    def prepare(self, mode, arguments, data):
        return True
    def install(self, data):
        return True
    def upgrade(self, arguments, data):
        return True

    def undo(self):
        if self.stopped:
            self.start()

class Apache(Service):
    display_name = "Apache"
    service_name = "apache2"

    etc_dir = "/etc/apache2"
    template_dir = "installation/templates/apache"

    def __init__(self):
        self.template_path = os.path.join(
            installation.root_dir, self.template_dir,
            "site.%s" % installation.config.access_scheme)
        self.site_enabled = False
        self.default_site_disabled = False

    def get_version(self):
        output = subprocess.check_output([installation.prereqs.apache2ctl.path, "-v"])
        match = re.search("Server version:\s*Apache/([^\s\n]*)", output, re.M)
        if not match:
            return None
        return match.group(1)

    def prepare(self, mode, arguments, data):
        if installation.config.auth_mode == "critic":
            pass_auth = "On"
        else:
            pass_auth = "Off"

        data["installation.apache.pass_auth"] = pass_auth

        return True

    def restart(self):
        if not self.stop():
            return False
        time.sleep(1)
        return self.start()

    def setup(self):
        version = self.get_version()
        if version and version.startswith("2.2."):
            self.site_suffix = ""
            self.default_site = "default"
        else:
            self.site_suffix = ".conf"
            self.default_site = "000-default"

        self.target_path = os.path.join(
            self.etc_dir, "sites-available", "critic-main%s" % self.site_suffix)

    def install(self, data):
        self.setup()

        process_configuration_file(
            "install", data, self.template_path, self.target_path)

        subprocess.check_call([installation.prereqs.a2enmod.path, "expires"])
        subprocess.check_call([installation.prereqs.a2enmod.path, "rewrite"])
        subprocess.check_call([installation.prereqs.a2enmod.path, "wsgi"])

        subprocess.check_call([installation.prereqs.a2ensite.path, "critic-main"])
        self.site_enabled = True

        output = subprocess.check_output(
            [installation.prereqs.a2dissite.path, self.default_site],
            env={ "LANG": "C" })
        if ("Site %s disabled." % self.default_site) in output:
            self.default_site_disabled = True

        return self.restart()

    def upgrade(self, arguments, data):
        self.setup()

        # If the configuration file doesn't exist, we're probably migrating the
        # system from one web server to another, so run the whole installation
        # procedure instead.
        if not os.path.isfile(self.target_path):
            return install(data)

        process_configuration_file(
            "upgrade", data, self.template_path, self.target_path, """\
The Apache site definition is about to be updated.  Please check that no local
modifications are being overwritten.

  Current version: %(current)s
  Updated version: %(updated)s

Please note that if the modifications are not installed, the system is likely
to break.
""")

        return True

    def undo(self):
        if self.site_enabled:
            subprocess.check_call(
                [installation.prereqs.a2dissite.path, "critic-main"])

            if self.default_site_disabled:
                subprocess.check_call(
                    [installation.prereqs.a2ensite.path, self.default_site])

            self.restart()

class nginx(Service):
    display_name = service_name = "nginx"

    etc_dir = "/etc/nginx"
    template_dir = "installation/templates/nginx"

    def __init__(self):
        self.site_enabled = False
        self.default_site_disabled = False
        self.template_path = os.path.join(
            installation.root_dir, self.template_dir,
            "site.%s" % installation.config.access_scheme)
        self.target_path = os.path.join(
            self.etc_dir, "sites-available/critic-main")
        self.enabled_path = os.path.join(
            self.etc_dir, "sites-enabled/critic-main")
        self.default_site_path = os.path.join(
            self.etc_dir, "sites-enabled/default")

    def install(self, data):
        process_configuration_file(
            "install", data, self.template_path, self.target_path)

        os.symlink(self.target_path, self.enabled_path)
        self.site_enabled = True

        if os.path.islink(self.default_site_path):
            os.unlink(self.default_site_path)
            self.default_site_disabled = True

        return self.restart()

    def upgrade(self, arguments, data):
        # If the configuration file doesn't exist, we're probably migrating the
        # system from one web server to another, so run the whole installation
        # procedure instead.
        if not os.path.isfile(self.target_path):
            return install(data)

        process_configuration_file(
            "upgrade", data, self.template_path, self.target_path, """\
The nginx site definition is about to be updated.  Please check that no local
modifications are being overwritten.

  Current version: %(current)s
  Updated version: %(updated)s

Please note that if the modifications are not installed, the system is likely
to break.
""")

        return True

    def undo(self):
        if self.site_enabled:
            os.unlink(self.enabled_path)

            if self.default_site_disabled:
                os.symlink(
                    os.path.join(self.etc_dir, "sites-available/default"),
                    self.default_site_path)

            self.restart()

class uWSGIBackend(Service):
    display_name = "uWSGI"
    service_name = "uwsgi"

    etc_dir = "/etc/uwsgi"
    template_dir = "installation/templates/uwsgi"

    def __init__(self):
        self.app_enabled = False
        self.template_path = os.path.join(
            installation.root_dir, self.template_dir, "app.backend.ini")
        self.target_path = os.path.join(
            self.etc_dir, "apps-available/critic-backend-main.ini")
        self.enabled_path = os.path.join(
            self.etc_dir, "apps-enabled/critic-backend-main.ini")

    def install(self, data):
        process_configuration_file(
            "install", data, self.template_path, self.target_path)

        os.symlink(self.target_path, self.enabled_path)
        self.app_enabled = True

        return self.restart()

    def upgrade(self, arguments, data):
        # If the configuration file doesn't exist, we're probably migrating the
        # system from one web server to another, so run the whole installation
        # procedure instead.
        if not os.path.isfile(self.target_path):
            return install(data)

        process_configuration_file(
            "upgrade", data, self.template_path, self.target_path, """\
The uWSGI back-end app definition is about to be updated.  Please check that
no local modifications are being overwritten.

  Current version: %(current)s
  Updated version: %(updated)s

Please note that if the modifications are not installed, the system is likely
to break.
""")

        return True

    def undo(self):
        if self.app_enabled:
            os.unlink(self.enabled_path)
            self.restart()

class uWSGIFrontend(Service):
    display_name = "uWSGI"
    service_name = "uwsgi"

    etc_dir = "/etc/uwsgi"
    template_dir = "installation/templates/uwsgi"

    def __init__(self):
        self.app_enabled = False
        self.template_path = os.path.join(
            installation.root_dir, self.template_dir,
            "app.frontend.ini.%s" % installation.config.access_scheme)
        self.target_path = os.path.join(
            self.etc_dir, "apps-available/critic-frontend-main.ini")
        self.enabled_path = os.path.join(
            self.etc_dir, "apps-enabled/critic-frontend-main.ini")

    def install(self, data):
        process_configuration_file(
            "install", data, self.template_path, self.target_path)

        os.symlink(self.target_path, self.enabled_path)
        self.app_enabled = True

        return self.restart()

    def upgrade(self, arguments, data):
        # If the configuration file doesn't exist, we're probably migrating the
        # system from one web server to another, so run the whole installation
        # procedure instead.
        if not os.path.isfile(self.target_path):
            return install(data)

        process_configuration_file(
            "upgrade", data, self.template_path, self.target_path, """\
The uWSGI front-end app definition is about to be updated.  Please check that
no local modifications are being overwritten.

  Current version: %(current)s
  Updated version: %(updated)s

Please note that if the modifications are not installed, the system is likely
to break.
""")

        return True

    def undo(self):
        if self.app_enabled:
            os.unlink(self.enabled_path)
            self.restart()

class Multiple():
    def __init__(self, *services):
        self.services = services

    def prepare(self, *args):
        return all(service.prepare(*args) for service in self.services)

    def install(self, *args):
        return all(service.install(*args) for service in self.services)

    def upgrade(self, *args):
        return all(service.upgrade(*args) for service in self.services)

    def undo(self):
        for service in self.services:
            service.undo()

    def start(self):
        return all(service.start() for service in self.services)
    def stop(self):
        return all(service.stop() for service in self.services)
    def restart(self):
        return all(service.restart() for service in self.services)

def prepare(mode, args, data):
    global arguments, instance

    arguments = args

    data["installation.httpd.username"] = "www-data"
    data["installation.httpd.groupname"] = "www-data"

    if installation.config.web_server_integration == "apache":
        instance = Apache()
        backend_service = Apache.service_name
    elif installation.config.web_server_integration == "uwsgi":
        instance = Multiple(uWSGIFrontend(), uWSGIBackend())
        backend_service = uWSGIBackend.service_name
    elif installation.config.web_server_integration == "nginx+uwsgi":
        instance = Multiple(nginx(), uWSGIBackend())
        backend_service = uWSGIBackend.service_name
    else:
        return True

    data["installation.httpd.backend_service"] = backend_service

    return instance.prepare(mode, arguments, data)

def install(data):
    if instance:
        return instance.install(data)
    return True

def upgrade(arguments, data):
    if instance:
        return instance.upgrade(arguments, data)
    return True

def undo():
    if instance:
        instance.undo()

    map(os.unlink, created_file)

    for target, backup in renamed:
        os.rename(backup, target)

def finish(mode, arguments, data):
    for target, backup in renamed:
        os.unlink(backup)

def start():
    if instance:
        return instance.start()
    return True

def stop():
    if instance:
        return instance.stop()
    return True
