with frontend.signin():
    # Only available if extension support has been enabled.
    frontend.page("manageextensions", expected_http_status=404)
