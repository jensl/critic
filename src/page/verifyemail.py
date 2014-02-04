# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import page.utils

def renderVerifyEmail(req, db, user):
    if user.isAnonymous():
        raise page.utils.NeedLogin(req)
    elif req.user != user.name:
        raise page.utils.DisplayMessage("Invalid use!")

    email = req.getParameter("email")
    verification_token = req.getParameter("token")

    cursor = db.cursor()
    cursor.execute("""SELECT id
                        FROM useremails
                       WHERE uid=%s
                         AND email=%s
                         AND verification_token=%s""",
                   (user.id, email, verification_token))

    row = cursor.fetchone()

    if not row:
        raise page.utils.DisplayMessage("Invalid verification token!")

    email_id = row[0]

    cursor.execute("""UPDATE useremails
                         SET verified=TRUE
                       WHERE id=%s""",
                   (email_id,))

    db.commit()

    raise page.utils.MovedTemporarily("/home?email_verified=%d" % email_id)
