import time

services = {}

with_class = testing.expect.with_class
extract_text = testing.expect.extract_text

def check_services(services, restarted=frozenset()):
    if isinstance(restarted, basestring):
        restarted = frozenset([restarted])

    def checker(document):
        expected = set(services.keys())

        for service_tr in document.findAll("tr", attrs=with_class("service")):
            td_name = service_tr.find("td", attrs=with_class("name"))
            td_pid = service_tr.find("td", attrs=with_class("pid"))
            td_rss = service_tr.find("td", attrs=with_class("rss"))

            name = str(extract_text(td_name))
            pid = extract_text(td_pid)
            rss = extract_text(td_rss)

            # These only start up fully when extensions are enabled.
            if name.startswith("extension"):
                continue

            try:
                pid = int(pid)
            except ValueError:
                if pid == "(not running)":
                    testing.logger.error("Service %r is not running!" % name)
                else:
                    testing.logger.error(
                        "Service %r has unexpected PID value: %r" % (name, pid))
            else:
                if rss == "N/A":
                    testing.logger.error("Service %r is not running "
                                         "(and the PID value is stale...)!"
                                         % name)

            if name in restarted:
                if pid == services[name]:
                    testing.logger.error(
                        "Service %r not restarted as expected!" % name)
            elif name in services:
                testing.expect.check(services[name], pid,
                                     message="service unexpectedly restarted")

            if name in expected:
                expected.remove(name)

            services[name] = pid

        if expected:
            testing.logger.error("Service(s) have gone missing: %r"
                                 % ", ".join(expected))

    return checker

with frontend.signin():
    services = {}

    frontend.page(
        "services",
        expect={
            "document_title": testing.expect.document_title(u"Services"),
            "content_title": testing.expect.paleyellow_title(0, u"Services"),
            "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                "administrator"),
            "script_user": testing.expect.script_user(instance.user("admin")),
            "services": check_services(services)
        })

    all_services = set(["manager"])

    for service_name in services.keys():
        if service_name not in ("manager", "extensiontasks") \
                and not service_name.startswith("wsgi:"):
            all_services.add(service_name)

            frontend.operation(
                "restartservice",
                data={ "service_name": service_name })

            frontend.page(
                "services",
                expect={ "services": check_services(services, service_name) })

    # Need to give the last service(s) restarted some time to actually start up;
    # otherwise they might receive their TERM signal before they register a
    # signal handler.
    time.sleep(0.5)

    frontend.operation(
        "restartservice",
        data={ "service_name": "manager" })

    # Need to give the service manager some time to actually restart.  Or rather
    # time to stop; once it has stopped, the /services page has code that waits
    # (up to 10 seconds) for it to start up again, should it not be up and
    # running already.
    time.sleep(0.5)

    frontend.page(
        "services",
        expect={ "services": check_services(services, all_services) })
