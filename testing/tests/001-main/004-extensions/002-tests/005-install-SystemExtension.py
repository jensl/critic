def check_extension(installed):
    def check(document):
        tr_items = document.findAll("tr", attrs={ "class": "item" })

        for tr_item in tr_items:
            td_name = tr_item.find("td", attrs={ "class": "name" })
            testing.expect.check("Extension:", td_name.string)

            td_value = tr_item.find("td", attrs={ "class": "value" })
            span_name = td_value.find("span", attrs={ "class": "name" })

            if span_name.contents[0].string != "SystemExtension":
                # Wrong extension.
                continue

            testing.expect.check(1, len(span_name.contents))

            span_installed = td_value.find("span", attrs={ "class": "installed" })
            if installed:
                testing.expect.check(" [installed]", span_installed.string)
            elif span_installed:
                testing.expect.check("<no installed indicator>",
                                     "<found installed indicator>")

            return
        else:
            testing.expect.check("<SystemExtension entry>",
                                 "<expected content not found>")

    return check

def check_helloworld(document):
    testing.expect.check("Hello world!\n", document)

try:
    instance.execute(
        ["sudo", "mkdir", "/var/lib/critic/extensions",
         "&&",
         "sudo", "cp", "-R", "~/critic/testing/input/SystemExtension",
         "/var/lib/critic/extensions",
         "&&",
         "sudo", "chown", "-R", "critic.critic",
         "/var/lib/critic/extensions",
         "&&",
         "sudo", "chmod", "-R", "u+rwX,go+rX",
         "/var/lib/critic/extensions"])
except testing.InstanceError as error:
    raise testing.TestFailure(error.message)

with frontend.signin("alice"):
    frontend.page(
        "manageextensions",
        expect={ "system_extension": check_extension(installed=False) })

    frontend.operation(
        "installextension",
        data={ "extension_name": "SystemExtension" })

    frontend.page(
        "manageextensions",
        expect={ "system_extension": check_extension(installed=True) })

    frontend.operation(
        "check",
        data={})

    frontend.page(
        "extension-resource/SystemExtension/HelloWorld.txt",
        expected_content_type="text/plain",
        expect={ "hello_world": check_helloworld })

frontend.page(
    "manageextensions",
    expect={ "system_extension": check_extension(False) })
