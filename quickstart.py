#!/usr/bin/env python3.6
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

import asyncio
import os
import sys

root_dir = os.path.abspath(os.path.dirname(__file__))

sys.path.insert(0, os.path.join(root_dir, "src"))

import quickstart

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(quickstart.main(root_dir)))
    except KeyboardInterrupt:
        pass


# def shadowVirtualEnv(src, dst):
#     for name in os.listdir(src):
#         if name != "bin":
#             os.symlink(os.path.join(src, name), os.path.join(dst, name))
#     src_bin = os.path.join(src, "bin")
#     dst_bin = os.path.join(dst, "bin")
#     os.mkdir(dst_bin)
#     for name in os.listdir(src_bin):
#         src_name = os.path.join(src_bin, name)
#         dst_name = os.path.join(dst_bin, name)
#         if os.path.islink(src_name):
#             os.symlink(src_name, dst_name)
#         elif os.path.isfile(src_name):
#             try:
#                 with open(src_name, "r", encoding="utf8") as src_file:
#                     lines = src_file.readlines()
#             except UnicodeDecodeError:
#                 shutil.copy(src_name, dst_name)
#             else:
#                 if lines[0].startswith("#!" + src_bin):
#                     lines[0] = "#!" + dst_bin + lines[0][len("#!" + src_bin) :]
#                 with open(dst_name, "w", encoding="utf8") as dst_file:
#                     dst_file.writelines(lines)
#                 shutil.copymode(src_name, dst_name)
