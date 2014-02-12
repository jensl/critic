# Only available if extension support has been enabled.  (The body of the
# message is quite long, and particularly interesting to check here.)
expected_message = testing.expect.message("Extension support not enabled", None)

frontend.page(
    "manageextensions",
    expect={ "message": expected_message })
