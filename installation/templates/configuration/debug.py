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

# True if this is a development installation of the system; False if it is a
# production installation.  Causes stack traces from unexpected exceptions to be
# displayed to all users rather than only to those with the "developer" role.
# Also changes the favicon and the color of the "Opera" text in page headers
# from red to black.
IS_DEVELOPMENT = %(installation.config.is_development)r

# True if this is an installation by the automatic testing framework.
IS_TESTING = %(installation.config.is_testing)r

# True if this is an instance started using the installation/quickstart.py
# script.
IS_QUICKSTART = %(installation.config.is_quickstart)r

# Directory to write code coverage results to.  If None, code coverage is not
# written, and more importantly, not measured in the first place.
COVERAGE_DIR = %(installation.config.coverage_dir)r
