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

def prepare(arguments):
    return True

BLACKLIST = set([ "install.py",
                  "installation",
                  "dbschema.sql",
                  "dbschema.comments.sql",
                  "path.pgsql",
                  "comments.pgsql",
                  ".git",
                  ".gitignore" ])

created_dir = []
created_file = []
copied_files = 0

def execute():
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

            if name not in BLACKLIST:
                if copy(name):
                    process(name)

    process()

    print "Copied %d files into %s ..." % (copied_files, target_dir)

    return True

def undo():
    map(os.unlink, reversed(created_file))

    try:
        map(os.rmdir, reversed(created_dir))
    except:
        print repr(reversed(created_dir))
        raise
