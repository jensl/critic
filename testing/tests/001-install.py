# Start instance and install (and upgrade, optionally) Critic with the default
# arguments.
instance.start()
instance.install(repository)
instance.upgrade()

body = """\
This is a test mail.

-- critic"""

instance.criticctl(["send-email"], stdin_data=body)
expect_system_mail("Critic test email", body)
