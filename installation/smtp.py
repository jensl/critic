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

import installation

host = None
port = None
username = None
password = None
use_ssl = None
use_starttls = None

def add_arguments(mode, parser):
    parser.add_argument("--smtp-host", help="SMTP server hostname (or IP)")
    parser.add_argument("--smtp-port", help="SMTP server port")
    parser.add_argument("--smtp-no-auth", action="store_true", help="no SMTP authentication required")
    parser.add_argument("--smtp-username", help="SMTP authentication username")
    parser.add_argument("--smtp-password", help="SMTP authentication password")

    # Using smtplib.SMTP_SSL()
    parser.add_argument("--smtp-ssl", dest="smtp_use_ssl", action="store_const", const=True,
                        help="use SSL(/TLS) when connecting to SMTP server")
    parser.add_argument("--smtp-no-ssl-tls", dest="smtp_use_ssl", action="store_const", const=False,
                        help="don't use SSL(/TLS) when connecting to SMTP server")

    # Using smtplib.SMTP() + starttls()
    parser.add_argument("--smtp-starttls", dest="smtp_use_starttls", action="store_const", const=True,
                        help="use STARTTLS when connecting to SMTP server")
    parser.add_argument("--smtp-no-starttls", dest="smtp_use_starttls", action="store_const", const=False,
                        help="don't use STARTTLS when connecting to SMTP server")

    parser.add_argument("--skip-testmail", dest="skip_testmail", action="store_const", const=True,
                        help="do not send a test e-mail to verify that given SMTP settings actually work")

def prepare(mode, arguments, data):
    global host, port, username, password, use_ssl, use_starttls, skip_testmail

    if mode == "install" or "installation.smtp.host" not in data:
        print """
Critic Installation: SMTP
=========================

Critic needs an SMTP server to use for outgoing email traffic.  Emails
are sent to regular Critic users to notify about changes in reviews, as
well as to the system administrator to alert about problems.
"""

        host = "localhost"
        use_ssl = False
        use_starttls = False

        def valid_port(value):
            try:
                if not (0 < int(value) < 65536): raise Exception
            except:
                return "must be a valid TCP port number"

        first = True

        if arguments.smtp_use_ssl and arguments.smtp_use_starttls:
            print "Invalid arguments: only one of --smtp-ssl and --smtp-starttls can be enabled."
            return False

        while True:
            if first and arguments.smtp_use_ssl is not None:
                use_ssl = arguments.smtp_use_ssl
            else:
                use_ssl = installation.input.yes_or_no("Use SSL when connecting to the SMTP server?", default=use_ssl)

            if not use_ssl:
                if first and arguments.smtp_use_starttls is not None:
                    use_starttls = arguments.smtp_use_starttls
                else:
                    use_starttls = installation.input.yes_or_no("Use STARTTLS when connecting to the SMTP server?", default=use_starttls)

            if first and arguments.smtp_host:
                host = arguments.smtp_host
            else:
                host = installation.input.string("SMTP host:", default=host)

            if first and arguments.smtp_port:
                error = valid_port(arguments.smtp_port)
                if error:
                    print "Invalid --smtp-port argument: %s." % error
                    return False

                port = arguments.smtp_port
            else:
                if port is None:
                    if use_ssl: port = "465"
                    else: port = "25"

                port = installation.input.string("SMTP port:", default=port, check=valid_port)

            need_password = False

            if first and arguments.smtp_username:
                username = arguments.smtp_username
                need_password = True
            elif not arguments.smtp_no_auth \
                    and installation.input.yes_or_no("Does the SMTP server require authentication?",
                                                     default=username is not None):
                username = installation.input.string("SMTP username:", default=username)
                need_password = True

            if need_password:
                if first and arguments.smtp_password:
                    password = arguments.smtp_password
                else:
                    password = installation.input.password("SMTP password:", default=password, twice=False)

            print

            if not arguments.skip_testmail and installation.input.yes_or_no("Do you want to send a test email to verify the SMTP configuration?",
                                            default=True):
                import smtplib
                import email.mime.text
                import email.header

                recipient = installation.input.string("To which email address?", default=installation.admin.email)
                failed = None

                try:
                    try:
                        if use_ssl:
                            connection = smtplib.SMTP_SSL(host, port, timeout=5)
                        else:
                            connection = smtplib.SMTP(host, port, timeout=5)
                    except:
                        failed = "Couldn't connect to the SMTP server."
                        raise

                    if use_starttls:
                        try:
                            connection.starttls()
                        except:
                            failed = "Failed to start TLS."
                            raise

                    if username is not None:
                        try:
                            connection.login(username, password)
                        except:
                            failed = "Failed to login."
                            raise

                    message = email.mime.text.MIMEText("This is the configuration test email from Critic.",
                                                       "plain", "us-ascii")

                    message["From"] = email.header.Header("Critic System <%s>" % installation.system.email)
                    message["To"] = email.header.Header(recipient)
                    message["Subject"] = email.header.Header("Test email from Critic")

                    try:
                        connection.sendmail(installation.system.email, [recipient], message.as_string())
                    except:
                        failed = "Failed to send the email."
                        raise

                    print
                    print "Test email sent to %s." % recipient
                    print
                except Exception, exception:
                    if not failed:
                        failed = str(exception)

                if failed:
                    print """
Couldn't send the test email:

  %s

Please check the configuration!
""" % failed
                elif installation.input.yes_or_no("Did the test email arrive correctly?") \
                        or not installation.input.yes_or_no("Do you want to modify the configuration?", default=True):
                    break
            else:
                break

            first = False

        port = int(port)

        data["installation.smtp.host"] = host
        data["installation.smtp.port"] = port
        data["installation.smtp.username"] = username
        data["installation.smtp.password"] = password
        data["installation.smtp.use_ssl"] = use_ssl
        data["installation.smtp.use_starttls"] = use_starttls
    else:
        host = data["installation.smtp.host"]
        port = data["installation.smtp.port"]
        username = data["installation.smtp.username"]
        password = data["installation.smtp.password"]
        use_ssl = data["installation.smtp.use_ssl"]
        use_starttls = data["installation.smtp.use_starttls"]

    return True
