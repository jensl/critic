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

import installation
import sys
import os
import os.path
import shutil
import hashlib
import errno

BLACKLIST = set([ "install.py",
                  "upgrade.py",
                  "installation",
                  "dbschema.sql",
                  "dbschema.comments.sql",
                  "path.pgsql",
                  "comments.pgsql",
                  ".git",
                  ".gitignore" ])

def blacklisted(name):
    path = os.path.dirname(name)
    while path:
        if path in BLACKLIST: return True
        path = os.path.dirname(path)
    if name in BLACKLIST: return True
    elif name.endswith(".pyc"): return True
    elif name.endswith(".pyo"): return True
    else: return False

created_dir = []
created_file = []
renamed = []
copied_files = 0
modified_files = 0
sources_modified = False
resources_modified = False

def getFileSHA1(git, commit_sha1, path):
    lstree = installation.process.check_output([git, "ls-tree", commit_sha1, path]).strip()

    if lstree:
        lstree_mode, lstree_type, lstree_sha1, lstree_path = lstree.split()

        assert lstree_type == "blob"
        assert lstree_path == path

        return lstree_sha1
    else:
        return None

def install(data):
    source_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    target_dir = installation.paths.install_dir

    def copy(path):
        global copied_files

        source = os.path.join(source_dir, path)
        target = os.path.join(target_dir, path)

        if os.path.isdir(source):
            os.mkdir(target, 0755)
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
            copied_files += 1
            return False

    def process(path=""):
        for entry in os.listdir(os.path.join(source_dir, path)):
            name = os.path.join(path, entry)

            if not blacklisted(name) and copy(name):
                process(name)

    process()

    print "Copied %d files into %s ..." % (copied_files, target_dir)

    return True

def upgrade(arguments, data):
    source_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    target_dir = data["installation.paths.install_dir"]

    git = data["installation.prereqs.git"]

    old_sha1 = data["sha1"]
    new_sha1 = installation.process.check_output([git, "rev-parse", "HEAD"]).strip()

    def isResource(path):
        return path.endswith(".css") or path.endswith(".js") or path.endswith(".txt")

    def remove(path):
        source_path = os.path.join(source_dir, path)
        target_path = os.path.join(target_dir, path)
        backup_path = os.path.join(os.path.dirname(target_path), "_" + os.path.basename(target_path))

        if not os.path.isfile(target_path): return

        old_file_sha1 = getFileSHA1(git, old_sha1, path)
        current_file_sha1 = hashlib.sha1(open(target_path).read()).hexdigest()

        if old_file_sha1 != current_file_sha1:
            def generateVersion(label, path):
                if label == "installed":
                    source = installation.process.check_output([git, "cat-file", "blob", old_file_sha1])
                    with open(path, "w") as target: target.write(source)

            update_query = installation.utils.UpdateModifiedFile(
                message="""\
A source file is about to be removed, but the existing source file
appears to have been edited since it was installed.

  Installed version: %(installed)s
  Current version  : %(current)s

Not removing the file can cause unpredictable results.
""",
                versions={ "installed": target_path + ".org",
                           "current": target_path },
                options=[ ("r", "remove the file"),
                          ("k", "keep the file"),
                          ("d", ("installed", "current")) ],
                generateVersion=generateVersion)

            if update_query.prompt() == "r":
                print "Removing file: %s" % path
                if not arguments.dry_run:
                    os.rename(target_path, backup_path)
                    renamed.append((target_path, backup_path))

    def copy(path):
        global copied_files, modified_files
        global resources_modified, sources_modified

        source_path = os.path.join(source_dir, path)
        target_path = os.path.join(target_dir, path)
        backup_path = os.path.join(os.path.dirname(target_path), "_" + os.path.basename(target_path))

        if not os.path.isfile(source_path):
            remove(path)
            return

        if os.path.isfile(source_path) and os.path.isdir(target_path):
            print """
The directory

  %s

is about to be deleted because a file is about to be installed in its
place.  Please make sure it doesn't contain anything that shouldn't be
deleted.
"""

            if not installation.input.yes_or_no("Do you want to delete the directory?", default=False):
                return False

            print "Removing directory: %s" % path
            if not arguments.dry_run:
                os.rename(target_path, backup_path)
                renamed.append((target_path, backup_path))

        if not os.path.isfile(target_path):
            print "New file: %s" % path
            if not arguments.dry_run:
                try: os.makedirs(os.path.dirname(target_path), 0755)
                except OSError, error:
                    if error.errno == errno.EEXIST: pass
                    else: raise
                shutil.copyfile(source_path, target_path)
                created_file.append(target_path)
                if path.startswith("hooks/"):
                    mode = 0755
                else:
                    mode = 0644
                os.chmod(target_path, mode)
            copied_files += 1
            if isResource(path):
                resources_modified = True
            else:
                sources_modified = True
        else:
            old_file_sha1 = getFileSHA1(git, old_sha1, path)
            new_file_sha1 = getFileSHA1(git, new_sha1, path)

            current_file_sha1 = installation.process.check_output([git, "hash-object", target_path]).strip()

            if current_file_sha1 != new_file_sha1:
                if current_file_sha1 != old_file_sha1:
                    def generateVersion(label, path):
                        if label == "installed":
                            source = installation.process.check_output([git, "cat-file", "blob", old_file_sha1])
                            with open(target_path + ".org", "w") as target: target.write(source)
                        elif label == "updated":
                            shutil.copyfile(source_path, target_path + ".new")

                    update_query = installation.utils.UpdateModifiedFile(
                        message="""\
A source file is about to be updated, but the existing source file
appears to have been edited since it was installed.

  Installed version: %(installed)s
  Current version  : %(current)s
  Updated version  : %(updated)s

Not installating the updated version can cause unpredictable results.
""",
                        versions={ "installed": target_path + ".org",
                                   "current": target_path,
                                   "updated": target_path + ".new" },
                        options=[ ("i", "install the updated version"),
                                  ("k", "keep the current version"),
                                  ("do", ("installed", "current")),
                                  ("dn", ("current", "updated")) ],
                        generateVersion=generateVersion)

                    install_file = update_query.prompt() == "i"
                else:
                    install_file = True

                if install_file:
                    print "Updated file: %s" % path
                    if not arguments.dry_run:
                        os.rename(target_path, backup_path)
                        renamed.append((target_path, backup_path))
                        shutil.copyfile(source_path, target_path)
                        created_file.append(target_path)
                        if path.startswith("hooks/"):
                            mode = 0755
                        else:
                            mode = 0644
                        os.chmod(target_path, mode)
                    modified_files += 1
                    if isResource(path):
                        resources_modified = True
                    else:
                        sources_modified = True

    differences = installation.process.check_output([git, "diff", "--numstat", "%s..%s" % (old_sha1, new_sha1)])

    for line in differences.splitlines():
        added, deleted, path = map(str.strip, line.split(None, 3))
        if not blacklisted(path):
            if copy(path) is False:
                return False

    if copied_files == 0 and modified_files == 0:
        print "No new or modified source files."

    data["sha1"] = new_sha1

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
