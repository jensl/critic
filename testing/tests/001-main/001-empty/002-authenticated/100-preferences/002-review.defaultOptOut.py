# Check existence of preference review.defaultOptOut, added by
#
#   http://critic-review.org/r/40

def check_heading(document):
    headings = document.findAll("td", attrs={ "class": "heading" })

    for heading in headings:
        if heading.find(text="review.defaultOptOut:"):
            return

    testing.expect.check("<preference heading>",
                         "<expected content not found>")

def check_input(document):
    input = document.find("input", attrs={ "name": "review.defaultOptOut" })

    if not input:
        testing.expect.check("<preference input>",
                             "<expected content not found>")

    testing.expect.check("checkbox", input["type"])
    testing.expect.check(False, input.has_key("checked"))
    testing.expect.check("false", input["critic-default"])

with frontend.signin():
    frontend.page("config",
                  expect={ "preference_heading": check_heading,
                           "preference_input": check_input })
