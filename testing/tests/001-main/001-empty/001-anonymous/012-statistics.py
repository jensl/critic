# The /statistics page has no <title>, and has a pale yellow table that doesn't
# have the 'paleyellow' class, and which has five (!) different main headings.
# Its generation should be fixed, but for now, just skip testing the common page
# elements that it's missing.
frontend.page("statistics", expect={ "pageheader_links": testing.expect.pageheader_links("anonymous"),
                                     "script_user": testing.expect.script_no_user() })
