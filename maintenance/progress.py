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

__prefix = ""
__current = 0
__total = 0
__previous = ""

def __output(string=None):
    global __prefix, __current, __total, __previous

    if string is None:
        percent = int(round((100.0 * __current) / __total))
        string = "%s [%3d %%]" % (__prefix, percent)

    if string != __previous:
        sys.stdout.write("\r%s%s" % (string, " " * (len(__previous) - len(string))))
        sys.stdout.flush()

        __previous = string

def start(total, prefix=""):
    global __prefix, __current, __total, __previous

    __prefix = prefix
    __current = 0
    __total = total
    __previous = ""

    if total: __output()

def update(count=1):
    global __current

    __current += count
    __output()

def end(message):
    __output(__prefix + message)
    sys.stdout.write("\n")

def write(string):
    __output(string)
    sys.stdout.write("\n")
    __output()

if __name__ == "__main__":
    import time

    start(1000, prefix="Testing: ")

    for index in range(200):
        time.sleep(0.01)
        update(5)

    end("Finished!")
