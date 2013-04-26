with frontend.signin("alice"):
    frontend.page("nothandled", expected_http_status=404)
