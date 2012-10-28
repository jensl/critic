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

from sys import argv, stderr
from time import time
from re import compile

CONTEXT_LINES = 3
RESYNC_THRESHOLD = 2

file1 = open(argv[1])
file2 = open(argv[2])

lineno1 = 0
lineno2 = -1

stacked1 = []
stacked2 = []

re_ignore = compile("^\\s*$|^\\s*{\\s*$|^\\s*}\\s*$")

def readline1():
    global file1, lineno1, stacked1
    lineno1 += 1
    if stacked1: return stacked1.pop(0)
    else: return file1.readline()

def readline2():
    global file2, lineno2
    lineno2 += 1
    if stacked2: return stacked2.pop(0)
    else: return file2.readline()

while True:
    line1 = readline1()
    line2 = readline2()

    #print "! line1=%r" % line1
    #print "! line2=%r" % line2

    if not line1 and not line2: break

    if not line1:
        start = lineno2
        extra = []
        while line2:
            extra.append(line2)
            line2 = readline2()
        print "@@ -%d,%d +%d,%d @@" % (lineno1, 0, start, len(extra))
        for line in extra: print "+%s" % line,
        break

    if not line2:
        start = lineno1
        extra = []
        while line1:
            extra.append(line1)
            line1 = readline1()
        print "@@ -%d,%d +%d,%d @@" % (start, len(extra), lineno2, 0)
        for line in extra: print "-%s" % line,
        break

    if not line2:
        while line1:
            print "-%s" % line1,
            line1 = readline1()
        break

    if line1 == line2: continue

    start1 = lineno1
    lines1 = [line1]
    table1 = { line1: [lineno1] }
    leads1 = []

    start2 = lineno2
    lines2 = [line2]
    table2 = { line2: [lineno2] }
    leads2 = []

    try:
        #print "%r != %r" % (line1, line2)

        while True:
            line1 = readline1()
            line2 = readline2()

            #print "line1=%r" % line1
            #print "line2=%r" % line2

            lines1.append(line1)
            table1.setdefault(line1, []).append(lineno1)

            lines2.append(line2)
            table2.setdefault(line2, []).append(lineno2)

            continued1 = set()
            continued2 = set()

            if leads1:
                for lead_index in range(len(leads1)):
                    lead = leads1[lead_index]
                    if line2 == lines1[lead[0] + lead[1]]:
                        continued1.add(lead[0] + lead[1])
                        lead[1] += 1
                        if lead[1] == RESYNC_THRESHOLD:
                            print "@@ -%d,%d +%d,%d @@" % (start1, lead[0], start2, len(lines2) - lead[1])
                            if lead[0] != 0:
                                for line in lines1[:lead[0]]: print "-%s" % line,
                            for line in lines2[:-lead[1]]: print "+%s" % line,
                            stack1 = lines1[lead[0]:]
                            stacked1[0:0] = stack1
                            lineno1 -= len(stack1)
                            stack2 = lines2[-lead[1]:]
                            stacked2[0:0] = stack2
                            lineno2 -= len(stack2)
                            raise Exception
                    else:
                        #print "leads1: %r != %r" % (line2, lines1[lead[0] + lead[1]])
                        leads1[lead_index] = None
                #print "* leads1: %r" % leads1
                leads1 = filter(None, leads1)
                #print "* leads1: %r" % leads1

            if leads2:
                for lead_index in range(len(leads2)):
                    lead = leads2[lead_index]
                    if line1 == lines2[lead[0] + lead[1]]:
                        continued2.add(lead[0] + lead[1])
                        lead[1] += 1
                        if lead[1] == RESYNC_THRESHOLD:
                            print "@@ -%d,%d +%d,%d @@" % (start1, len(lines1) - lead[1], start2, lead[0])
                            for line in lines1[:-lead[1]]: print "-%s" % line,
                            if lead[0] != 0:
                                for line in lines2[:lead[0]]: print "+%s" % line,
                            stack1 = lines1[-lead[1]:]
                            stacked1[0:0] = stack1
                            lineno1 -= len(stack1)
                            stack2 = lines2[lead[0]:]
                            stacked2[0:0] = stack2
                            lineno2 -= len(stack2)
                            raise Exception
                    else:
                        #print "leads2: %r != %r" % (line1, lines2[lead[0] + lead[1]])
                        leads2[lead_index] = None
                #print "* leads2: %r" % leads2
                leads2 = filter(None, leads2)
                #print "* leads2: %r" % leads2

            linenos = table1.get(line2)
            if linenos:
                #print repr(continued1)
                for lineno in linenos:
                    if not re_ignore.match(line2):
                        lead = [lineno - start1, 1]
                        print "@@ -%d,%d +%d,%d @@" % (start1, lead[0], start2, len(lines2) - lead[1])
                        if lead[0] != 0:
                            for line in lines1[:lead[0]]: print "-%s" % line,
                        for line in lines2[:-lead[1]]: print "+%s" % line,
                        stack1 = lines1[lead[0]:]
                        stacked1[0:0] = stack1
                        lineno1 -= len(stack1)
                        stack2 = lines2[-lead[1]:]
                        stacked2[0:0] = stack2
                        lineno2 -= len(stack2)
                        raise Exception
                    elif lineno - start1 not in continued1:
                        leads1.append([lineno - start1, 1])

            linenos = table2.get(line1)
            if linenos:
                #print repr(continued2)
                for lineno in linenos:
                    if not re_ignore.match(line1):
                        lead = [lineno - start2, 1]
                        print "@@ -%d,%d +%d,%d @@" % (start1, len(lines1) - lead[1], start2, lead[0])
                        for line in lines1[:-lead[1]]: print "-%s" % line,
                        if lead[0] != 0:
                            for line in lines2[:lead[0]]: print "+%s" % line,
                        stack1 = lines1[-lead[1]:]
                        stacked1[0:0] = stack1
                        lineno1 -= len(stack1)
                        stack2 = lines2[lead[0]:]
                        stacked2[0:0] = stack2
                        lineno2 -= len(stack2)
                        raise Exception
                    elif lineno - start2 not in continued2:
                        leads2.append([lineno - start2, 1])

            #print "leads1: %r" % leads1
            #print "leads2: %r" % leads2
    except Exception:
        #print "resync: %d / %d" % (lineno1, lineno2)
        #print repr(stacked1)
        #print repr(stacked2)
        pass
