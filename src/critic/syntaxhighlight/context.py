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

# import os

# from critic import syntaxhighlight

# This is just for sanity.
MIN_CONTEXT_LENGTH = 5
# This is also the maximum length of the database column, so it's a hard limit
# in an already installed system.
MAX_CONTEXT_LENGTH = 256


# def importCodeContexts(db, sha1, language):
#     codecontexts_path = syntaxhighlight.generateHighlightPath(sha1, language) + ".ctx"

#     if os.path.isfile(codecontexts_path):
#         contexts_values = []

#         for line in open(codecontexts_path):
#             line = line.strip()

#             first_line, last_line, context = line.split(" ", 2)
#             if len(context) > MAX_CONTEXT_LENGTH:
#                 context = context[: MAX_CONTEXT_LENGTH - 3] + "..."
#             contexts_values.append((sha1, context, int(first_line), int(last_line)))

#         cursor = db.cursor()
#         cursor.execute("DELETE FROM codecontexts WHERE sha1=%s", [sha1])
#         cursor.executemany(
#             "INSERT INTO codecontexts (sha1, context, first_line, last_line) VALUES (%s, %s, %s, %s)",
#             contexts_values,
#         )
#         db.commit()

#         os.unlink(codecontexts_path)

#         return len(contexts_values)
#     else:
#         return 0
