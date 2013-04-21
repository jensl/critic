# This is the commit that adds testing/input/binary.
COMMIT = "47c6cea51af517107c403d96810fce946825aacc"

def check_description(document):
    actual = "<expected content not found>"

    for row in document.findAll("tr"):
        cells = row.findAll("td")
        if len(cells) >= 2 \
                and cells[0].has_key("class") \
                and cells[0]["class"] == "path" \
                and cells[0].a \
                and cells[0].a.string \
                and cells[0].a.string.endswith("/binary") \
                and cells[1].i \
                and cells[1].i.string:
            actual = cells[1].i.string
            break

    testing.expect.check(u"binary", actual)

with frontend.signin():
    frontend.page("showcommit",
                  params={ "repository": "critic",
                           "sha1": COMMIT },
                  expect={ "description": check_description })
