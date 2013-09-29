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
import shutil
import errno
import py_compile
import subprocess

import installation

created_dir = []
created_file = []
renamed = []
copied_files = 0
modified_files = 0
sources_modified = False
resources_modified = False

def compile_file(filename):
    global created_file
    if not filename.endswith(".py"):
        return True
    try:
        path = os.path.join(installation.paths.install_dir, filename)
        with installation.utils.as_critic_system_user():
            py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as error:
        print """
ERROR: Failed to compile %s:\n%s
""" % (filename, error)
        return False
    else:
        created_file.append(path + "c")
        return True

def install(data):
    source_dir = os.path.join(installation.root_dir, "src")
    target_dir = installation.paths.install_dir

    # Note: this is an array since it's modified in a nested scope.
    compilation_failed = []

    def copy(path):
        global copied_files

        source = os.path.join(source_dir, path)
        target = os.path.join(target_dir, path)

        if os.path.isdir(source):
            os.mkdir(target, 0755)
            os.chown(target, installation.system.uid, installation.system.gid)
            created_dir.append(target)
            return True
        else:
            shutil.copyfile(source, target)
            created_file.append(target)
            if path.startswith("hooks/"):
                mode = 0755
            else:
                mode = 0644
            os.chmod(target, mode)
            os.chown(target, installation.system.uid, installation.system.gid)
            copied_files += 1
            if not compile_file(path):
                compilation_failed.append(path)
            return False

    def process(path=""):
        for entry in os.listdir(os.path.join(source_dir, path)):
            name = os.path.join(path, entry)

            if copy(name):
                process(name)

    process()
    sys.path.insert(0, installation.paths.install_dir)

    if compilation_failed:
        return False

    print "Copied %d files into %s ..." % (copied_files, target_dir)

    return True

def upgrade(arguments, data):
    source_dir = installation.root_dir
    target_dir = data["installation.paths.install_dir"]

    # Note: this is an array since it's modified in a nested scope.
    compilation_failed = []

    uid = installation.system.uid
    gid = installation.system.gid

    def chown(directory):
        os.chown(directory, uid, gid)
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if os.path.isdir(path):
                chown(path)
            elif path.endswith(".pyc"):
                os.chown(path, uid, gid)
            elif path.endswith(".pyo"):
                os.unlink(path)

    chown(target_dir)

    git = data["installation.prereqs.git"]

    old_sha1 = data["sha1"]
    new_sha1 = subprocess.check_output([git, "rev-parse", "HEAD"],
                                       cwd=installation.root_dir).strip()

    old_has_src = installation.utils.get_tree_sha1(git, old_sha1, "src")

    def isResource(path):
        return path.endswith(".css") or path.endswith(".js") or path.endswith(".txt")

    def remove(old_source_path, target_path):
        full_target_path = os.path.join(target_dir, target_path)
        backup_path = os.path.join(os.path.dirname(full_target_path),
                                   "_" + os.path.basename(target_path))

        if not os.path.isfile(full_target_path):
            return

        old_file_sha1 = installation.utils.get_file_sha1(
            git, old_sha1, old_source_path)
        current_file_sha1 = installation.utils.hash_file(
            git, full_target_path)

        assert old_file_sha1 is not None

        if old_file_sha1 != current_file_sha1:
            def generateVersion(label, path):
                if label == "installed":
                    source = subprocess.check_output(
                        [git, "cat-file", "blob", old_file_sha1],
                        cwd=installation.root_dir)
                    with open(path, "w") as target:
                        target.write(source)

            update_query = installation.utils.UpdateModifiedFile(
                arguments,
                message="""\
A source file is about to be removed, but the existing source file
appears to have been edited since it was installed.

  Installed version: %(installed)s
  Current version  : %(current)s

Not removing the file can cause unpredictable results.
""",
                versions={ "installed": full_target_path + ".org",
                           "current": full_target_path },
                options=[ ("r", "remove the file"),
                          ("k", "keep the file"),
                          ("d", ("installed", "current")) ],
                generateVersion=generateVersion)

            if update_query.prompt() == "r":
                remove_file = True
            else:
                remove_file = False
        else:
            remove_file = True

        if remove_file:
            print "Removing file: %s" % target_path
            if not arguments.dry_run:
                os.rename(full_target_path, backup_path)
                renamed.append((full_target_path, backup_path))

                if target_path.endswith(".py"):
                    if os.path.isfile(full_target_path + "c"):
                        os.unlink(full_target_path + "c")
                    if os.path.isfile(full_target_path + "o"):
                        os.unlink(full_target_path + "o")

    def copy(old_source_path, new_source_path, target_path):
        global copied_files, modified_files
        global resources_modified, sources_modified

        full_source_path = os.path.join(source_dir, new_source_path)
        full_target_path = os.path.join(target_dir, target_path)
        backup_path = os.path.join(os.path.dirname(full_target_path),
                                   "_" + os.path.basename(target_path))

        if not os.path.isfile(full_source_path):
            remove(old_source_path, target_path)
            return

        if os.path.isfile(full_source_path) and os.path.isdir(full_target_path):
            print """
The directory

  %s

is about to be deleted because a file is about to be installed in its
place.  Please make sure it doesn't contain anything that shouldn't be
deleted.
""" % full_target_path

            if not installation.input.yes_or_no("Do you want to delete the directory?", default=False):
                return False

            print "Removing directory: %s" % target_path
            if not arguments.dry_run:
                os.rename(full_target_path, backup_path)
                renamed.append((full_target_path, backup_path))

        if not os.path.isfile(full_target_path):
            print "New file: %s" % target_path
            if not arguments.dry_run:
                try: os.makedirs(os.path.dirname(full_target_path), 0755)
                except OSError as error:
                    if error.errno == errno.EEXIST: pass
                    else: raise
                shutil.copyfile(full_source_path, full_target_path)
                created_file.append(full_target_path)
                if target_path.startswith("hooks/"):
                    mode = 0755
                else:
                    mode = 0644
                os.chmod(full_target_path, mode)
            copied_files += 1
            if isResource(target_path):
                resources_modified = True
            else:
                sources_modified = True
        else:
            old_file_sha1 = installation.utils.get_file_sha1(
                git, old_sha1, old_source_path)
            new_file_sha1 = installation.utils.get_file_sha1(
                git, new_sha1, new_source_path)

            assert old_file_sha1 is not None
            assert new_file_sha1 is not None

            current_file_sha1 = installation.utils.hash_file(
                git, full_target_path)

            if current_file_sha1 != new_file_sha1:
                if current_file_sha1 != old_file_sha1:
                    def generateVersion(label, path):
                        if label == "installed":
                            source = subprocess.check_output(
                                [git, "cat-file", "blob", old_file_sha1],
                                cwd=installation.root_dir)
                            with open(full_target_path + ".org", "w") as target:
                                target.write(source)
                        elif label == "updated":
                            shutil.copyfile(full_source_path,
                                            full_target_path + ".new")

                    update_query = installation.utils.UpdateModifiedFile(
                        arguments,
                        message="""\
A source file is about to be updated, but the existing source file
appears to have been edited since it was installed.

  Installed version: %(installed)s
  Current version  : %(current)s
  Updated version  : %(updated)s

Not installing the updated version can cause unpredictable results.
""",
                        versions={ "installed": full_target_path + ".org",
                                   "current": full_target_path,
                                   "updated": full_target_path + ".new" },
                        options=[ ("i", "install the updated version"),
                                  ("k", "keep the current version"),
                                  ("do", ("installed", "current")),
                                  ("dn", ("current", "updated")) ],
                        generateVersion=generateVersion)

                    install_file = update_query.prompt() == "i"
                else:
                    install_file = True

                if install_file:
                    print "Updated file: %s" % target_path
                    if not arguments.dry_run:
                        os.rename(full_target_path, backup_path)
                        renamed.append((full_target_path, backup_path))
                        shutil.copyfile(full_source_path, full_target_path)
                        created_file.append(full_target_path)
                        if target_path.startswith("hooks/"):
                            mode = 0755
                        else:
                            mode = 0644
                        os.chmod(full_target_path, mode)
                        if not compile_file(target_path):
                            compilation_failed.append(target_path)
                    modified_files += 1
                    if isResource(target_path):
                        resources_modified = True
                    else:
                        sources_modified = True

    differences = subprocess.check_output(
        [git, "diff", "--numstat", "%s..%s" % (old_sha1, new_sha1)],
        cwd=installation.root_dir)

    changed_paths = set()

    for line in differences.splitlines():
        _, _, path = map(str.strip, line.split(None, 3))
        if path.startswith("src/"):
            changed_paths.add(path[len("src/"):])
        elif not old_has_src:
            if os.path.isfile(os.path.join(target_dir, path)):
                changed_paths.add(path)

    for path in sorted(changed_paths):
        if old_has_src:
            old_source_path = os.path.join("src", path)
        else:
            old_source_path = path
        if copy(old_source_path=old_source_path,
                new_source_path=os.path.join("src", path),
                target_path=path) is False:
            return False

    if compilation_failed:
        return False

    if copied_files == 0 and modified_files == 0:
        print "No new or modified source files."

    return True

def undo():
    map(os.unlink, reversed(created_file))
    map(os.rmdir, reversed(created_dir))

    for target, backup in renamed:
        os.rename(backup, target)

def finish():
    for target, backup in renamed:
        if os.path.isdir(backup): shutil.rmtree(backup)
        else: os.unlink(backup)
