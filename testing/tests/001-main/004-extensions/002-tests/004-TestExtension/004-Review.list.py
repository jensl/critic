with frontend.signin("alice"):
    result = frontend.operation("Review.list", data={})

    for failed in result["failed"]:
        logger.error("Review.list: %(test)s: %(message)s" % failed)

    for passed in result["passed"]:
        logger.debug("Review.list: %(test)s: passed (%(result)s)" % passed)
