# Download the README file in the root directory in the initial released commit.
expected_README = """\
Critic
======

This is the code review system, Critic.
"""
actual_README = frontend.page(
    "download/README",
    params={ "repository": "critic",
             "sha1": "f4c6e5fc09de47f7eb1a623cbc8820f67967d558" },
    expected_content_type="text/plain")
testing.expect.check(expected_README, actual_README)

# Download the resources/basic.js file in the initial released commit.  We won't
# bother to check that the content is correct (it's too big to inline in this
# test,) so just check that the content type is correctly guessed.
frontend.page(
    "download/resources/basic.js",
    params={ "repository": "critic",
             "sha1": "2c7d6f87c11670f3c371cca0580553f01ec94340" },
    expected_content_type="text/javascript")

# Download the resources/basic.js file in the initial released commit, this time
# with an abbreviated SHA-1 sum.
frontend.page(
    "download/resources/basic.js",
    params={ "repository": "critic",
             "sha1": "2c7d6f87c11" },
    expected_content_type="text/javascript")

# Attempt to download the README file in the root directory but specify a SHA-1
# that isn't a blob, but rather the initial released commit's SHA-1.  This
# should fail.
frontend.page(
    "download/README",
    params={ "repository": "critic",
             "sha1": "aa15bc746d3340bda912a1cc4759b332b9adff55" },
    expected_http_status=404)

# Attempt to download the README file in the root directory but specify a SHA-1
# that doesn't exist at all in the repository.
frontend.page(
    "download/README",
    params={ "repository": "critic",
             "sha1": "0000000000000000000000000000000000000000" },
    expected_http_status=404)

# Attempt to download the README file in the root directory but specify a SHA-1
# that isn't a valid SHA-1.
frontend.page(
    "download/README",
    params={ "repository": "critic",
             "sha1": "0123456789abcdefghijklmnopqrstuvwxzy" },
    expected_http_status=404)

# Use a bogus repository parameter.
frontend.page(
    "download/README",
    params={ "repository": "notcritic",
             "sha1": "f4c6e5fc09de47f7eb1a623cbc8820f67967d558" },
    expected_http_status=404)

# Omit the sha1 parameter.
frontend.page(
    "download/README",
    params={ "repository": "critic" },
    expected_http_status=400)

# Omit the repository parameter.
frontend.page(
    "download/README",
    params={ "sha1": "f4c6e5fc09de47f7eb1a623cbc8820f67967d558" },
    expected_http_status=400)
