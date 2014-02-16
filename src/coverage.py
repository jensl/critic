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
import trace
import errno
import tempfile
import shutil
import re
import json

def call(context, fn, *args, **kwargs):
    import configuration

    if not configuration.debug.COVERAGE_DIR:
        return fn(*args, **kwargs)

    context_dir = os.path.join(configuration.debug.COVERAGE_DIR, context)

    try:
        os.makedirs(context_dir)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise

    output_dir = tempfile.mkdtemp(dir=context_dir)
    counts = output_dir + ".counts"
    tracer = trace.Trace(count=1, trace=0, outfile=counts)

    try:
        return tracer.runfunc(fn, *args, **kwargs)
    finally:
        results = tracer.results()
        results.write_results(show_missing=False, coverdir=output_dir)
        shutil.rmtree(output_dir)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser("Critic Code Coverage Collection")
    parser.add_argument("--coverage-dir")
    parser.add_argument("--critic-dir", action="append")

    arguments = parser.parse_args()

    ignore_dirs = filter(None, sys.path)

    coverage_dir = arguments.coverage_dir
    sys.path[:0] = arguments.critic_dir

    data = { "contexts": [] }

    for context in os.listdir(coverage_dir):
        context_dir = os.path.join(coverage_dir, context)

        if not os.path.isdir(context_dir):
            continue

        context_index = len(data["contexts"])
        data["contexts"].append(context)

        tracer = trace.Trace()
        results = tracer.results()

        for filename in os.listdir(context_dir):
            if filename.endswith(".counts"):
                counts = os.path.join(context_dir, filename)
                results.update(trace.Trace(infile=counts).results())
                os.unlink(counts)

        results.write_results(show_missing=False, coverdir=context_dir)

        for filename in os.listdir(context_dir):
            if filename.endswith(".cover"):
                module_filename = filename[:-6].replace(".", "/") + ".py"
                if os.path.isfile(module_filename):
                    counts = {}
                    with open(os.path.join(context_dir, filename)) as coverage:
                        lines = coverage.read().splitlines()
                    executed = []
                    for index, line in enumerate(lines):
                        match = re.match(" *\d+:", line)
                        if match:
                            executed.append(index)
                    data.setdefault(module_filename, {})[context] = executed

    json.dump(data, sys.stdout)

    print
