def check_extension(installed):
    def check(document):
        tr_item = document.find("tr", attrs={ "class": "item" })

        td_name = tr_item.find("td", attrs={ "class": "name" })
        testing.expect.check("Extension:", td_name.string)

        td_value = tr_item.find("td", attrs={ "class": "value" })

        span_name = td_value.find("span", attrs={ "class": "name" })
        testing.expect.check("TestExtension", span_name.contents[0].string)
        testing.expect.check(" hosted by Alice von Testing", span_name.contents[1])

        span_installed = td_value.find("span", attrs={ "class": "installed" })
        if installed:
            testing.expect.check(" [installed]", span_installed.string)
        elif span_installed:
            testing.expect.check("<no installed indicator>",
                                 "<found installed indicator>")

    return check

try:
    instance.execute(
        ["sudo", "mkdir", "~alice/CriticExtensions",
         "&&",
         "sudo", "cp", "-R", "~/critic/testing/input/TestExtension",
         "~alice/CriticExtensions",
         "&&",
         "sudo", "chown", "-R", "alice.critic", "~alice/CriticExtensions",
         "&&",
         "sudo", "chmod", "-R", "u+rwX,go+rX", "~alice/CriticExtensions"])

    instance.execute(
        ["sudo", "-H", "-u", "alice", "git", "init",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "add", ".",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "commit", "-mInitial",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "checkout", "-b", "version/stable",
         "&&",
         "sudo", "su", "-c", "'echo stable:1 > version.txt'", "alice",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "add", "version.txt",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "commit", "-mStable:1",
         "&&",
         "sudo", "su", "-c", "'echo stable:2 > version.txt'", "alice",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "commit", "-mStable:2", "version.txt",
         "&&",
         "sudo", "-H", "-u", "alice", "git", "checkout", "master",
         "&&",
         "sudo", "su", "-c", "'echo live > version.txt'", "alice"],
        cwd="~alice/CriticExtensions/TestExtension")
except testing.InstanceError as error:
    raise testing.TestFailure(error.message)

with frontend.signin("alice"):
    frontend.page(
        "manageextensions",
        expect={ "test_extension": check_extension(False) })

    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.page(
        "manageextensions",
        expect={ "test_extension": check_extension(True) })

frontend.page(
    "manageextensions",
    expect={ "test_extension": check_extension(False) })
