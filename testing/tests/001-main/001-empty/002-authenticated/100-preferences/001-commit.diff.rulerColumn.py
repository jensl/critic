# Check existence of preference commit.diff.rulerColumn, added by
#
#   http://critic-review.org/r/57

def check_heading(document):
    headings = document.findAll("td", attrs={ "class": "heading" })

    for heading in headings:
        if heading.find(text="commit.diff.rulerColumn:"):
            return

    testing.expect.check("<preference heading>",
                         "<expected content not found>")

def check_input(document):
    input = document.find("input", attrs={ "name": "commit.diff.rulerColumn" })

    if not input:
        testing.expect.check("<preference input>",
                             "<expected content not found>")

    testing.expect.check("number", input["type"])
    testing.expect.check("0", input["value"])
    testing.expect.check("0", input["critic-default"])

with frontend.signin():
    frontend.page("config",
                  expect={ "preference_heading": check_heading,
                           "preference_input": check_input })
