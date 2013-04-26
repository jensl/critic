import re

def check_compilation(document):
    testing.expect.check(
        expected="""\
Extension failure: returned 1
Failed to load 'error\\.compilation\\.js':
  SyntaxError: Strict mode function may not have duplicate parameter names""",
        actual=document,
        equal=re.match)

def check_runtime(document):
    testing.expect.check(
        expected="""\
Extension failure: returned 1
Failed to call 'error\\.runtime\\.js::test\\(\\)':
  CriticError: nosuchuser: no such user
    new CriticUser\\(\\) at <Library>/critic-user\\.js:\\d+
    test\\(\\) at <Extension>/error\\.runtime\\.js:\\d+
    <program code> at <Library>/critic-launcher\\.js:\\d+""",
        actual=document,
        equal=re.match)

with frontend.signin("alice"):
    frontend.page(
        "error.compilation",
        expected_content_type="text/plain",
        expected_http_status=500,
        expect={ "message": check_compilation })

    frontend.page(
        "error.runtime",
        expected_content_type="text/plain",
        expected_http_status=500,
        expect={ "message": check_runtime })
