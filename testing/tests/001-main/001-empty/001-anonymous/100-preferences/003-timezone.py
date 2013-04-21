# Check existence of preference review.defaultOptOut, added by
#
#   http://critic-review.org/r/40

def check_heading(document):
    headings = document.findAll("td", attrs={ "class": "heading" })

    for heading in headings:
        if heading.find(text="timezone:"):
            return

    testing.expect.check("<preference heading>",
                         "<expected content not found>")

def check_select(document):
    select = document.find("select", attrs={ "name": "timezone" })

    if not select:
        testing.expect.check("<preference select>",
                             "<expected content not found>")

    testing.expect.check("Universal/UTC", select["critic-default"])

    option = select.find("option", attrs={ "selected": "selected" })

    if not option:
        testing.expect.check("<pre-selected option>",
                             "<expected content not found>")

    testing.expect.check("Universal/UTC", option["value"])
    testing.expect.check("UTC (UTC / UTC+00:00)", option.string)

frontend.page("config",
              expect={ "preference_heading": check_heading,
                       "preference_input": check_select })
