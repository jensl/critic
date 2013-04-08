import base
import dbutils

class InvalidParameterValue(base.Error):
    def __init__(self, expected):
        self.expected = expected

class Optional(object):
    def __init__(self, actual):
        self.actual = actual

class ListOf(object):
    def __init__(self, actual):
        self.actual = actual

def check_integer(value, what="value"):
    try:
        value = int(value)
    except ValueError:
        raise InvalidParameterValue("an integer %s" % what)
    else:
        return value

class Stateful(object):
    def __init__(self, req, db, user):
        self.req = req
        self.db = db
        self.user = user

class ReviewId(Stateful):
    def __call__(self, value):
        review_id = check_integer(value, "review id")

        try:
            review = dbutils.Review.fromId(self.db, review_id)
        except dbutils.NoSuchReview:
            raise InvalidParameterValue("a valid review id")

        return review
