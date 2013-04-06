import re

# This is an arbitrary (and fairly small) commit on master:
COMMIT = "927e2ba833cb0c9ce588b5f59c42bbb246e3e20c"

def check_rulerColumn(document):
    for script in document.findAll("script"):
        # Ignore external scripts.
        if script.has_key("src"):
            continue

        if re.match(r"var\s+rulerColumn\s*=\s*0;", script.string):
            break
    else:
        testing.expect.check("<rulerColumn script>",
                             "<expected content not found>")

frontend.page("critic/%s" % COMMIT,
              expect={ "rulerColumn_script": check_rulerColumn })
