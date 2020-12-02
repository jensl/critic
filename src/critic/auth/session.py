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

import aiohttp.web
import logging
from typing import Collection, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)

from critic import auth

from critic import api
from critic import dbaccess


def allowNoSession(req: aiohttp.web.BaseRequest) -> bool:
    """Check if the request is for an insecure path

    "Insecure" here means that unauthenticated/anonymous access should be
    allowed even if the system doesn't normally allow anonymous access."""
    if api.critic.settings().frontend.session_type == "cookie":
        # Login machinery must be accessible before being logged in.
        if req.path == "api/v1/sessions" and req.method == "POST":
            return True
        if req.path == "api/v1/sessions/current" and req.method == "GET":
            return True
    if api.critic.settings().users.allow_registration:
        # User creation machinery also, if user creation is enabled.
        if req.path == "api/v1/users" and req.method == "POST":
            return True
    # Disallow unauthenticated access to the API.
    if req.path.startswith("api/"):
        return False
    # Allow GET requests. Note that specific request handlers could still reject
    # the request, or redirect to a different path.
    return req.method == "GET"


def requestHTTPAuthentication():
    raise aiohttp.web.HTTPUnauthorized(
        headers={"www-authenticate": 'Basic realm="Critic"'}
    )


class Cookies(Protocol):
    def set_cookie(self, name: str, value: str, *, secure: bool) -> None:
        ...

    def del_cookie(self, name: str) -> None:
        ...


async def createSessionId(
    cookies: Cookies,
    user: api.user.User,
    authentication_labels: Optional[Collection[str]] = None,
    *,
    external_account: Optional[api.externalaccount.ExternalAccount] = None,
) -> None:
    sid = auth.getToken()
    if authentication_labels:
        labels = "|".join(sorted(authentication_labels))
    else:
        labels = ""

    critic = api.critic.getSession()

    async with critic.transaction() as cursor:
        await cursor.execute(
            """INSERT
                 INTO usersessions (key, uid, external_uid, labels)
               VALUES ({sid}, {user}, {external_account}, {labels})""",
            sid=sid,
            user=user,
            external_account=external_account,
            labels=labels,
        )

    cookies.set_cookie("sid", sid, secure=True)
    cookies.set_cookie("has_sid", "1", secure=False)


async def deleteSessionId(req: aiohttp.web.BaseRequest, cookies: Cookies) -> bool:
    sid = req.cookies.get("sid", None)

    if sid is None:
        return False

    cookies.del_cookie("sid")
    cookies.set_cookie("has_sid", "0", secure=False)

    critic = api.critic.getSession()

    async with critic.transaction() as cursor:
        await cursor.delete("usersessions", key=sid)

    return True


async def checkSession(req: aiohttp.web.BaseRequest) -> None:
    """Check if the request is part of a session and if so set req.user

    Raises an request.HTTPResponse exception if immediate action is required,
    otherwise sets req.user to non-None (but possibly to the anonymous user)
    and returns."""

    critic = api.critic.getSession()
    authdb = auth.Database.get()

    authentication_mode = api.critic.settings().frontend.authentication_mode
    allow_anonymous_user = api.critic.settings().users.allow_anonymous

    # Step 1: If the host web server is supposed to authenticate users, use the
    #         $REMOTE_USER environment variable.
    if authentication_mode == "host":
        # Strip white-space, since Apache is known to do this internally when
        # authenticating, but then passing on the original unstripped string to
        # us on success.
        username: str = req.headers["remote-user"].strip()
        if not username:
            # No REMOTE_USER variable.  If we support anonymous users, this is
            # fine, otherwise it indicates a configuration error.
            if allow_anonymous_user:
                return
            raise aiohttp.web.HTTPInternalServerError(
                text="Missing 'remote-user' header from reverse proxy!"
            )

        # We have a username.  Fetch the (or create a) matching user record.
        try:
            await critic.setActualUser(await api.user.fetch(critic, name=username))
        except api.user.InvalidName:
            async with api.transaction.start(critic) as transaction:
                modifier = await transaction.createUser(username, username, None)
            await critic.setActualUser(modifier.subject)
        return

    session_type = api.critic.settings().frontend.session_type
    session_max_age = api.critic.settings().frontend.session_max_age

    # Step 2: If cookie based sessions are used, check if there is a valid
    #         session cookie.
    if session_type == "cookie":
        sid = req.cookies.get("sid")
        if sid:
            async with api.critic.Query[
                Tuple[Optional[int], Optional[int], Optional[str], int]
            ](
                critic,
                """SELECT uid, external_uid, labels,
                          EXTRACT('epoch' FROM NOW() - atime) AS age
                     FROM usersessions
                    WHERE key={session_id}""",
                session_id=sid,
            ) as result:
                try:
                    (
                        user_id,
                        external_user_id,
                        session_labels,
                        session_age,
                    ) = await result.one()
                except dbaccess.ZeroRowsInResult:
                    user_id = external_user_id = session_labels = None
                    session_age = 0

            if user_id is not None or external_user_id is not None:
                if session_max_age is None or session_age < session_max_age:
                    # This is a valid session cookie.
                    if user_id is not None:
                        user = await api.user.fetch(critic, user_id)
                        if session_labels is None:
                            labels = await authdb.getAuthenticationLabels(user)
                        else:
                            labels = session_labels.split("|") if session_labels else ()
                        await critic.setActualUser(user)
                        critic.setAuthenticationLabels(labels)
                    if external_user_id is not None:
                        external_account = await api.externalaccount.fetch(
                            critic, external_user_id
                        )
                        await critic.setExternalAccount(external_account)
                    return

                # The session cookie is too old.  Delete it from the database.
                async with critic.transaction() as cursor:
                    await cursor.execute(
                        """DELETE
                             FROM usersessions
                            WHERE key={session_id}""",
                        session_id=sid,
                    )

            # The session cookie is not valid.  Delete it from the browser.
            # cookies.del_cookie("sid")
            # Also delete the has_sid cookie, if there is one.
            # cookies.del_cookie("has_sid")

        # elif req.cookies.get("has_sid") == "1":
        # The request had no session cookie, but had the has_sid cookie that
        # indicates the browser ought to have a sesssion cookie.  Typically,
        # this means a signed in user accesses a mixed HTTP/HTTPS system
        # over HTTP.  If so, redirect the user to HTTPS.

        # FIXME: redirect to secure (if desired)
        # req.ensureSecure()

        # The above call would have raised if a redirect was meaningful.  If
        # it didn't, the has_sid cookie is bogus, so delete it.
        # cookies.del_cookie("has_sid")

        # elif req.cookies.get("has_sid") == "0":
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
        # cookies.del_cookie("has_sid")

        # Do the redirect if anonymous access isn't allowed.  Also don't do
        # it on the actual login page.
        # if not allow_anonymous_user and req.path != "login":
        #     raise request.DisplayMessage(
        #         title="You have signed out",
        #         body="To use this system, you will need to sign in again.",
        #     )

    # Step 3(a): Check if there's a valid HTTP Authorization header (even if
    #            cookie based sessions are typically used.)  If there is such a
    #            header, we assume HTTP authentication was meant to be used, and
    #            respond with a 401 Unauthorized response if authentication
    #            using the header fails.
    try:
        authorization_header = req.headers["authorization"]
    except KeyError:
        pass
    else:
        await handle_authorization_header(req, authorization_header)
        return

    # Step 3(b): If the request has a "use_httpauth" cookie, request/require
    #            HTTP authentication.  This is a just a convenience feature for
    #            clients using HTTP stacks that only send credentials in
    #            response to server challenges.  (If cookie sessions are used,
    #            no such challenge would normally be returned, we'd rather
    #            redirect to the login page.)
    if req.cookies.get("use_httpauth"):
        requestHTTPAuthentication()
    # Also do this for requests with a "httpauth=yes" query parameter.
    if req.query.get("httpauth") == "yes":
        requestHTTPAuthentication()

    # Step 4: If anonymous access is supported or if it should be allowed as an
    #         exception for the accessed path, leave the session anonymous.
    if allow_anonymous_user or allowNoSession(req):
        return

    # Step 5: If HTTP authentication is required (i.e. no session cookies) then
    #         request that now.
    if session_type == "httpauth":
        requestHTTPAuthentication()

    # Step 6: Cookie based sessions are enabled, and not anonymous access.
    if not allowNoSession(req):
        raise aiohttp.web.HTTPForbidden(text="Valid user session required")


async def handle_authorization_header(
    req: aiohttp.web.BaseRequest, authorization_header: str
) -> None:
    import base64

    try:
        authtype, credentials_base64 = authorization_header.split(None, 1)
    except ValueError:
        # Header value not on "<TYPE> <CREDENTIALS>" form.
        raise aiohttp.web.HTTPBadRequest()

    username = password = token = None

    logger.debug(f"{authtype=} {credentials_base64=}")

    if authtype.lower() == "basic":
        try:
            credentials = base64.b64decode(credentials_base64.strip())
        except (ValueError, TypeError):
            # Not valid base64-encoded credentials.
            raise aiohttp.web.HTTPBadRequest()

        username_bytes, _, password_bytes = credentials.partition(b":")
        username = username_bytes.strip().decode()
        password = password_bytes.decode()
    elif authtype.lower() == "bearer":
        token = credentials_base64.strip()
        logger.debug(f"{token=}")
    else:
        # Unsupported authorization type.
        raise aiohttp.web.HTTPBadRequest()

    authdb = auth.Database.get()

    try:
        await authdb.performHTTPAuthentication(
            api.critic.getSession(), username=username, password=password, token=token
        )
    except auth.AuthenticationFailed as error:
        # Well-formed Authorization header, but bad credentials. Request new ones.
        logger.debug(f"{error=}")
        requestHTTPAuthentication()
