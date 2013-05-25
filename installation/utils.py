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

import os
import textwrap
import subprocess

import installation

class UpdateModifiedFile:
    def __init__(self, arguments, message, versions, options, generateVersion):
        """\
        Constructor.

        Arguments:

          arguments  Command-line arguments.
          message    Printed once.
          versions   Dictionary (label => path) of file versions involved.
          options    List of options to present to the user.
          prompt     Prompt printed when asking what to do.
        """

        self.__arguments = arguments
        self.__message = message
        self.__versions = versions
        self.__options = options
        self.__option_keys = [key for key, action in options]
        self.__option_map = dict((key, action) for key, action in options)
        self.__generateVersion = generateVersion
        self.__generated = []

    def printMessage(self):
        print self.__message % self.__versions

    def printOptions(self):
        alternatives = []

        for key, action in self.__options:
            if isinstance(action, str):
                alternatives.append("'%s' to %s" % (key, action))
            else:
                alternatives.append("'%s' to display the differences between the %s version and the %s version"
                                    % (key, action[0], action[1]))

        print textwrap.fill("Input %s and %s." % (", ".join(alternatives[:-1]), alternatives[-1]))
        print

    def displayDifferences(self, from_version, to_version):
        print
        print "=" * 80

        diff = installation.process.process(["diff", "-u", self.__versions[from_version], self.__versions[to_version]])
        diff.wait()

        print "=" * 80
        print

    def prompt(self):
        if self.__arguments.headless:
            # The first choice is typically "install updated version" or "remove
            # (obsolete) file" and is appropriate when --headless was used.
            return self.__options[0][0]

        try:
            for label, path in self.__versions.items():
                if not os.path.exists(path):
                    self.__generateVersion(label, path)
                    self.__generated.append(path)

            self.printMessage()

            while True:
                self.printOptions()

                def validResponse(value):
                    if value not in self.__option_keys:
                        return "please answer %s or %s" % (", ".join(self.__option_keys[:-1]), self.__option_keys[-1])

                response = installation.input.string("What do you want to do?", check=validResponse)
                action = self.__option_map[response]

                if isinstance(action, str):
                    print
                    return response

                from_version, to_version = action

                self.displayDifferences(from_version, to_version)
        finally:
            for path in self.__generated:
                os.unlink(path)

def update_from_template(arguments, data, template_path, target_path, message):
    git = data["installation.prereqs.git"]

    old_commit_sha1 = data["sha1"]
    new_commit_sha1 = subprocess.check_output([git, "rev-parse", "HEAD"]).strip()

    old_template = read_file(git, old_commit_sha1, template_path)
    new_template = read_file(git, new_commit_sha1, template_path)

    old_source = old_template.decode("utf-8") % data
    new_source = new_template.decode("utf-8") % data

    with open(target_path) as target_file:
        current_source = target_file.read().decode("utf-8")

    if current_source == new_source:
        # The current version is what we would install now.  Nothing to do.
        return
    elif old_source == current_source:
        # The current version is what we installed (or would have installed with
        # the old template and current settings.)  Update the target file
        # without asking.
        write_target = True
    else:
        def generate_version(label, path):
            if label == "installed":
                source = old_source
            elif label == "updated":
                source = new_source
            else:
                return
            write_file(path, source.encode("utf-8"))

        versions = """\
  Installed version: %(installed)s
  Current version:   %(current)s
  Updated version:   %(updated)s"""

        update_query = UpdateModifiedFile(
            arguments,
            message=message % { "versions": versions },
            versions={ "installed": target_path + ".org",
                       "current": target_path,
                       "updated": target_path + ".new" },
            options=[ ("i", "install the updated version"),
                      ("k", "keep the current version"),
                      ("do", ("installed", "current")),
                      ("dn", ("current", "updated")) ],
            generateVersion=generate_version)

        write_target = update_query.prompt() == "i"

    if write_target:
        print "Updated file: %s" % target_path

        if not arguments.dry_run:
            backup_path = os.path.join(os.path.dirname(target_path),
                                       ".%s.org" % os.path.basename(target_path))
            copy_file(target_path, backup_path)
            with open(target_path, "w") as target_file:
                target_file.write(new_source.encode("utf-8"))
            return backup_path

def write_file(path, source):
    # Use os.open() with O_EXCL to avoid trampling some existing file.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w") as target:
        target.write(source)

def copy_file(source_path, target_path):
    with open(source_path) as source:
        stat = os.fstat(source.fileno())
        # Use os.open() with O_EXCL to avoid trampling some existing file.
        fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w") as target:
            target.write(source.read())
            os.fchmod(target.fileno(), stat.st_mode)
            os.fchown(target.fileno(), stat.st_uid, stat.st_gid)

def hash_file(git, path):
    return installation.process.check_output([git, "hash-object", path]).strip()

def get_file_sha1(git, commit_sha1, path):
    lstree = installation.process.check_output([git, "ls-tree", commit_sha1, path]).strip()

    if lstree:
        lstree_mode, lstree_type, lstree_sha1, lstree_path = lstree.split()

        assert lstree_type == "blob"
        assert lstree_path == path

        return lstree_sha1
    else:
        return None

def read_file(git, commit_sha1, path):
    file_sha1 = get_file_sha1(git, commit_sha1, path)
    if file_sha1 is None:
        return None
    return installation.process.check_output(
        [git, "cat-file", "blob", file_sha1])

def as_critic_system_user():
    class Context:
        def __init__(self):
            self.__uid = os.getuid()
            self.__gid = os.getgid()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            os.seteuid(self.__uid)
            os.seteuid(self.__gid)
            return False

    context = Context()

    os.setegid(installation.system.gid)
    os.seteuid(installation.system.uid)

    return context
