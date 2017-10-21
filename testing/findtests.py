import os
import re
import fnmatch

import testing

TESTS = None
TESTS_BY_FILENAME = {}

def automaticDependencies(filename):
    this_dirname = os.path.dirname(filename)
    for test in TESTS:
        other_dirname = os.path.dirname(test.filename)
        if this_dirname.startswith(other_dirname):
            if os.path.sep not in other_dirname \
                    or len(other_dirname) < len(this_dirname):
                yield test

RE_DEPENDENCY = re.compile(r"#\s+@dependency\s+([^\s]+)")
RE_FLAG = re.compile(r"#\s+@flag\s+([-\w]+)")
RE_IGNORE = re.compile(r"(?:\s*#.*)?\s*$")

class Test(object):
    def __init__(self, filename):
        self.filename = filename
        self.groups = []
        dirname = filename
        while True:
            dirname, basename = os.path.split(dirname)
            if not dirname:
                break
            self.groups.insert(0, dirname)
        self.dependencies = set()
        self.flags = set()

        has_dependency_declarations = []

        def process_file(path):
            path = os.path.join("testing", "tests", path)
            if not os.path.isfile(path):
                return
            with open(path) as source_file:
                for index, line in enumerate(source_file):
                    match = RE_DEPENDENCY.match(line)
                    if match:
                        has_dependency_declarations.append(True)
                        dependency = match.group(1)
                        if dependency == "none":
                            pass
                        elif dependency not in TESTS_BY_FILENAME:
                            testing.logger.error(
                                "%s:%d: invalid depdency: %s"
                                % (filename, index + 1, dependency))
                        else:
                            self.dependencies.add(TESTS_BY_FILENAME[dependency])
                        continue
                    match = RE_FLAG.match(line)
                    if match:
                        self.flags.add(match.group(1))
                        continue
                    match = RE_IGNORE.match(line)
                    if not match:
                        break

        process_file(filename)

        dirname = filename
        while True:
            dirname = os.path.dirname(dirname)
            if not dirname:
                break
            process_file(os.path.join(dirname, "__init__.py"))

        if not has_dependency_declarations:
            self.dependencies.update(automaticDependencies(filename))

        TESTS.append(self)
        TESTS_BY_FILENAME[self.filename] = self

    def __str__(self):
        return self.filename
    def __hash__(self):
        return hash(self.filename)
    def __eq__(self, other):
        return self.filename == str(other)

    def __repr__(self):
        return "Test(%r): %r" % (self.filename, sorted([test.filename for test in self.dependencies]))

def findTests():
    global TESTS

    RE_TEST_FILENAME = re.compile(r"/\d\d\d-[^/]*\.py$")
    RE_IGNORE_FILENAME = re.compile(r"(?:/__init__.py|~)$")

    TESTS = []

    def traverse(dirname):
        for filename in sorted(os.listdir(dirname)):
            filename = os.path.join(dirname, filename)
            if os.path.isdir(filename):
                traverse(filename)
            elif RE_TEST_FILENAME.search(filename):
                Test(os.path.relpath(filename, "testing/tests"))
            elif not RE_IGNORE_FILENAME.search(filename):
                testing.logger.warning(
                    "%s: unexpected non-test file under testing/tests/"
                    % filename)

    traverse("testing/tests")

def filterPatterns(patterns):
    RE_LEADING_TESTS = re.compile("^(?:testing/)?tests(?:/|$)")

    patterns = [RE_LEADING_TESTS.sub("", pattern) for pattern in patterns]
    patterns = [pattern.rstrip("/") for pattern in patterns]
    patterns = list(filter(None, patterns))

    return patterns

def selectTests(patterns, strict, flags_on=set(), flags_off=set()):
    if TESTS is None:
        findTests()

    patterns = filterPatterns(patterns)

    if not patterns and not flags_on and not flags_off:
        return TESTS, set()

    selected = set()
    dependencies = set()

    def select(test, is_dependency=False):
        if test in selected:
            # Test already selected.
            return
        selected.add(test.filename)
        if strict:
            # Don't select dependencies when strict=True.
            return
        if is_dependency:
            dependencies.add(test.filename)
        for dependency in test.dependencies:
            select(dependency, True)

    for test in TESTS:
        if flags_on - test.flags:
            continue
        if flags_off & test.flags:
            continue

        if patterns:
            for pattern in patterns:
                filename = test.filename
                while filename:
                    if fnmatch.fnmatch(filename, pattern):
                        select(test)
                        break
                    if strict:
                        break
                    filename = os.path.dirname(filename)
                if test in selected:
                    break
        else:
            select(test)

    return [test for test in TESTS if test in selected], dependencies
