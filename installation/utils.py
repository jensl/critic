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

def hash_file(git, path):
    return installation.process.check_output([git, "hash-object", path]).strip()
