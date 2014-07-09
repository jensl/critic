# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Lindström, Opera Software ASA
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
import logging
import re
import json

def level_value(level):
    return getattr(logging, level.upper())

filter_level = level_value(sys.argv[1])
logfile_paths = sys.argv[2:]

def include_entry(entry_level):
    return filter_level <= level_value(entry_level)

HEADER = r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d\d\d -  *"

RE_ENTRY = re.compile(
    "{header}(([A-Z]+) - .*?)(?=$|\n{header}[A-Z]+ - )".format(header=HEADER),
    re.DOTALL)

data = {}

for logfile_path in logfile_paths:
    with open(logfile_path) as logfile:
        log = logfile.read()

    if os.path.isfile(logfile_path + ".skip"):
        with open(logfile_path + ".skip") as logfile_skip:
            skip = int(logfile_skip.read())
    else:
        skip = 0

    entries = []

    for index, match in enumerate(RE_ENTRY.finditer(log)):
        if index < skip:
            continue
        entry, entry_level = match.groups()
        if include_entry(entry_level):
            entries.append(entry)

    if entries:
        data[logfile_path] = entries

    skip = index + 1

    with open(logfile_path + ".skip", "w") as logfile_skip:
        logfile_skip.write(str(skip))

if data:
    json.dump(data, sys.stdout)
    sys.exit(0)

sys.exit(1)
