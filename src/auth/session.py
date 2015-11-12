# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import auth
import dbutils
import configuration
import request

def isInsecurePath(req):
    """Check if the request is for an insecure path

       "Insecure" here means that unauthenticated/anonymous access should be
       allowed even if the system doesn't normally allow anonymous access."""
    if configuration.base.SESSION_TYPE == "cookie":
        # Login machinery must be accessible before being logged in.
        if req.path in ("login", "validatelogin"):
            return True
    if configuration.base.ALLOW_USER_REGISTRATION:
        # User creation machinery also, if user creation is enabled.
        if req.path in ("createuser", "registeruser"):
            return True
    # Allow unauthenticated access to all static resources.
    if req.path.startswith("static-resource/"):
        return True
    return False

try:
    from customization.email import getUserEmailAddress
except ImportError:
    def getUserEmailAddress(_username):
        return None

def createSessionId(db, req, user, authentication_labels=None):
    sid = auth.getToken()
    if authentication_labels:
        labels = "|".join(sorted(authentication_labels))
    else:
        labels = ""

    with db.updating_cursor("usersessions") as cursor:
        cursor.execute("""INSERT INTO usersessions (key, uid, labels)
                               VALUES (%s, %s, %s)""",
                       (sid, user.id, labels))

    req.setCookie("sid", sid, secure=True)
    req.setCookie("has_sid", "1")

def deleteSessionId(db, req, user):
    sid = req.cookies.get("sid", None)

    if sid is None:
        return False

    req.deleteCookie("sid")
    req.setCookie("has_sid", "0")

    cursor = db.readonly_cursor()
    cursor.execute("""SELECT 1
                        FROM usersessions
                       WHERE key=%s
                         AND uid=%s""",
                   (sid, user.id))

    if not cursor.fetchone():
        # Not a valid session cookie..?
        return False

    with db.updating_cursor("usersessions") as cursor:
        cursor.execute("""DELETE
                            FROM usersessions
                           WHERE key=%s
                             AND uid=%s""",
                       (sid, user.id))

    return True

def checkSession(db, req):
    """Check if the request is part of a session and if so set req.user

       Raises an request.HTTPResponse exception if immediate action is required,
       otherwise sets req.user to non-None (but possibly to the anonymous user)
       and returns."""

    # Step 1: If the host web server is supposed to authenticate users, use the
    #         $REMOTE_USER environment variable.
    if configuration.base.AUTHENTICATION_MODE == "host":
        # Strip white-space, since Apache is known to do this internally when
        # authenticating, but then passing on the original unstripped string to
        # us on success.
        username = req.getEnvironment().get("REMOTE_USER", "").strip()
        if not username:
            # No REMOTE_USER variable.  If we support anonymous users, this is
            # fine, otherwise it indicates a configuration error.
            if configuration.base.ALLOW_ANONYMOUS_USER:
                db.setUser(dbutils.User.makeAnonymous())
                return
            raise request.MissingWSGIRemoteUser()

        # We have a username.  Fetch the (or create a) matching user record.
        try:
            db.setUser(dbutils.User.fromName(db, username))
        except dbutils.NoSuchUser:
            email = getUserEmailAddress(username)
            db.setUser(dbutils.User.create(
                db, username, username, email, email_verified=None))
        return

    # Step 2: If cookie based sessions are used, check if there is a valid
    #         session cookie.
    if configuration.base.SESSION_TYPE == "cookie":
        sid = req.cookies.get("sid")
        if sid:
            cursor = db.cursor()
            cursor.execute(
                """SELECT uid, labels, EXTRACT('epoch' FROM NOW() - atime) AS age
                     FROM usersessions
                    WHERE key=%s""",
                (sid,))

            row = cursor.fetchone()
            if row:
                user_id, labels, session_age = row

                if configuration.base.SESSION_MAX_AGE == 0 \
                        or session_age < configuration.base.SESSION_MAX_AGE:
                    # This is a valid session cookie.
                    user = dbutils.User.fromId(db, user_id)
                    if labels is None:
                        labels = auth.DATABASE.getAuthenticationLabels(user)
                    else:
                        labels = labels.split("|") if labels else ()
                    db.setUser(user, labels)
                    return

                # The session cookie is too old.  Delete it from the database.
                with db.updating_cursor("usersessions") as cursor:
                    cursor.execute("""DELETE FROM usersessions
                                            WHERE key=%s""",
                                   (sid,))

            # The session cookie is not valid.  Delete it from the browser.
            req.deleteCookie("sid")
            # Also delete the has_sid cookie, if there is one.
            req.deleteCookie("has_sid")

            # Since the session seems to have expired, offer the user to sign in
            # again by redirecting to the login page.  Signing in is optional
            # though, meaning the login page will have a "Continue anonymously"
            # link (if anonymous access is allowed.)
            #
            # Exception: Don't do this if /login is being requested.
            if req.allowRedirect(307) and req.path != "login":
                raise request.NeedLogin(req, optional=True)

        elif req.cookies.get("has_sid") == "1":
            # The request had no session cookie, but had the has_sid cookie that
            # indicates the browser ought to have a sesssion cookie.  Typically,
            # this means a signed in user accesses a mixed HTTP/HTTPS system
            # over HTTP.  If so, redirect the user to HTTPS.
            req.ensureSecure()

            # The above call would have raised if a redirect was meaningful.  If
            # it didn't, the has_sid cookie is bogus, so delete it.
            req.deleteCookie("has_sid")

        elif req.cookies.get("has_sid") == "0":
            # This indicates that the user just signed out.  If anonymous access
            # is not allowed, we'll redirect the user to the login page again,
            # which is sort of a bit unhelpful.
            #
            # Worse yet; if use of an external authentication provider is
            # enforced, the login page will redirect there, which might sign the
            # user back in, non-interactively.  In that case, signing out would
            # be impossible.
            #
            # So, instead, detect the sign-out and return a simple "you have
            # signed out" page in this case.

            # Delete the cookie.  This means that on reload, the user is
            # redirected to the login page again.  (This is to prevent the user
            # from getting stuck on this "you have signed out" page.)
            req.deleteCookie("has_sid")

            # Do the redirect if anonymous access isn't allowed.  Also don't do
            # it on the actual login page.
            if not configuration.base.ALLOW_ANONYMOUS_USER \
                    and req.path != "login":
                raise request.DisplayMessage(
                    title="You have signed out",
                    body="To use this system, you will need to sign in again.")

    # Step 3(a): Check if there's a valid HTTP Authorization header (even if
    #            cookie based sessions are typically used.)  If there is such a
    #            header, we assume HTTP authentication was meant to be used, and
    #            respond with a 401 Unauthorized response if authentication
    #            using the header fails.
    authorization_header = req.getRequestHeader("Authorization")
    if authorization_header:
        import base64

        try:
            authtype, base64_credentials = authorization_header.split(None, 1)
        except ValueError:
            authtype = "invalid"
        if authtype.lower() != "basic":
            raise request.RequestHTTPAuthentication()

        try:
            credentials = base64.b64decode(base64_credentials)
        except (ValueError, TypeError) as error:
            raise request.RequestHTTPAuthentication()

        username, _, password = credentials.partition(":")
        username = username.strip()

        if username and password:
            try:
                auth.DATABASE.performHTTPAuthentication(db, username, password)
                req.session_type = "httpauth"
                return
            except auth.AuthenticationFailed:
                pass

        raise request.RequestHTTPAuthentication()

    # Step 3(b): If the request has a "use_httpauth" cookie, request/require
    #            HTTP authentication.  This is a just a convenience feature for
    #            clients using HTTP stacks that only send credentials in
    #            response to server challenges.  (If cookie sessions are used,
    #            no such challenge would normally be returned, we'd rather
    #            redirect to the login page.)
    if req.cookies.get("use_httpauth"):
        raise request.RequestHTTPAuthentication()
    # Also do this for requests with a "httpauth=yes" query parameter.
    if req.getParameter("httpauth", "no") == "yes":
        raise request.RequestHTTPAuthentication()

    # Step 4: If anonymous access is supported or if it should be allowed as an
    #         exception for the accessed path, leave the session anonymous.
    if configuration.base.ALLOW_ANONYMOUS_USER or isInsecurePath(req):
        db.setUser(dbutils.User.makeAnonymous())
        req.session_type = None
        return

    # Step 5: If HTTP authentication is required (i.e. no session cookies) then
    #         request that now.
    if configuration.base.SESSION_TYPE == "httpauth":
        raise request.RequestHTTPAuthentication()

    # Step 6: Cookie based sessions are enabled, and not anonymous access.  If
    #         this is a POST or PUT request, respond with 403 Forbidden, and
    #         otherwise redirect to the login page.
    if not req.allowRedirect(307):
        raise request.Forbidden("Valid user session required")

    raise request.NeedLogin(req, optional=req.cookies.has_key("has_sid"))
