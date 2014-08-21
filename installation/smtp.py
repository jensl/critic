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
import json

import installation

host = None
port = None
username = None
password = None
use_ssl = None
use_starttls = None
use_system_mail_for_from_field = None

def add_arguments(mode, parser):
    if mode == "install":
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
        parser.add_argument("--smtp-system-mail-for-from-field", dest="smtp_use_system_mail_for_from_field", action="store_const", const=True,
                            help="use SYSTEM MAIL USER as value for From: field in all mails")
        parser.add_argument("--smtp-no-system-mail-for-from-field", dest="smtp_use_system_mail_for_from_field", action="store_const", const=False,
                            help="don't use SYSTEM MAIL USER as value for From: field in all mails")

        # Using smtplib.SMTP() + starttls()
        parser.add_argument("--smtp-starttls", dest="smtp_use_starttls", action="store_const", const=True,
                            help="use STARTTLS when connecting to SMTP server")
        parser.add_argument("--smtp-no-starttls", dest="smtp_use_starttls", action="store_const", const=False,
                            help="don't use STARTTLS when connecting to SMTP server")

        parser.add_argument("--skip-testmail", action="store_true",
                            help="do not send a test e-mail to verify that given SMTP settings actually work")
        parser.add_argument("--skip-testmail-check", action="store_true",
                            help="do not ask whether the test e-mail arrived correctly")

def prepare(mode, arguments, data):
    global host, port, username, password, use_ssl, use_starttls, use_system_mail_for_from_field

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
        use_system_mail_for_from_field = False

        def valid_port(value):
            try:
                if not (0 < int(value) < 65536):
                    raise ValueError
            except ValueError:
                return "must be a valid TCP port number"


        if mode == "install":
            if arguments.smtp_use_ssl and arguments.smtp_use_starttls:
                print "Invalid arguments: only one of --smtp-ssl and --smtp-starttls can be enabled."
                return False
            first = True
        else:
            # This case, an upgrade where installation.smtp.host is not recorded
            # in "data"; happens when upgrading from a pre-5f0389f commit to
            # 5f0389f or later.  Since upgrade.py doesn't have --smtp-* command
            # line arguments, ignore "arguments" variable and go straight to
            # manual input.
            first = False

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
            elif (not first or not arguments.smtp_no_auth) \
                    and installation.input.yes_or_no("Does the SMTP server require authentication?",
                                                     default=username is not None):
                username = installation.input.string("SMTP username:", default=username)
                need_password = True

            if need_password:
                if first and arguments.smtp_password:
                    password = arguments.smtp_password
                else:
                    password = installation.input.password("SMTP password:", default=password, twice=False)

            if first and arguments.smtp_use_system_mail_for_from_field is not None:
                use_system_mail_for_from_field = arguments.smtp_use_system_mail_for_from_field
            else:
                use_system_mail_for_from_field = installation.input.yes_or_no("Use SYSTEM MAIL USER as value for From: field in all mails?", default=use_system_mail_for_from_field)

            print

            if (not first or not arguments.skip_testmail) \
                    and installation.input.yes_or_no("Do you want to send a test email to verify the SMTP configuration?",
                                                     default=True if first else None):
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

                    try:
                        connection.quit()
                    except:
                        failed = "Failed to close connection."
                        raise

                    print
                    print "Test email sent to %s." % recipient
                    print
                except Exception as exception:
                    if not failed:
                        failed = str(exception)

                if failed:
                    print """
Couldn't send the test email:

  %s

Please check the configuration!
""" % failed
                elif (first and arguments.skip_testmail_check) \
                         or installation.input.yes_or_no("Did the test email arrive correctly?") \
                         or not installation.input.yes_or_no("Do you want to modify the configuration?", default=True):
                    break
            else:
                break

            first = False

        port = int(port)
    else:
        import configuration

        host = configuration.smtp.HOST
        port = configuration.smtp.PORT
        use_ssl = configuration.smtp.USE_SSL
        use_starttls = configuration.smtp.USE_STARTTLS

        credentials_path = os.path.join(configuration.paths.CONFIG_DIR,
                                        "configuration/smtp-credentials.json")
        try:
            with open(credentials_path) as credentials_file:
                credentials = json.load(credentials_file)

            username = credentials["username"]
            password = credentials["password"]
        except:
            username = getattr(configuration.smtp, "USERNAME")
            password = getattr(configuration.smtp, "PASSWORD")

    data["installation.smtp.host"] = host
    data["installation.smtp.port"] = port
    data["installation.smtp.username"] = json.dumps(username)
    data["installation.smtp.password"] = json.dumps(password)
    data["installation.smtp.use_ssl"] = use_ssl
    data["installation.smtp.use_starttls"] = use_starttls
    data["installation.smtp.use_system_mail_for_from_field"] = use_system_mail_for_from_field

    return True

def finish(mode, arguments, data):
    del data["installation.smtp.username"]
    del data["installation.smtp.password"]
