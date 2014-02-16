import api

class InvalidPreferenceItem(api.APIError):
    """Raised if an invalid preference item is used."""

    def __init__(self, item):
        """Constructor"""
        super(InvalidPreferenceItem, self).__init__(
            "Invalid preference item: %r" % item)

class Preference(object):
    def __init__(self, item, value, user, repository):
        self.__item = item
        self.__value = value
        self.__user = user
        self.__repository = repository

    def __bool__(self):
        return bool(self.__value)
    def __int__(self):
        return self.__value
    def __str__(self):
        return self.__value

    @property
    def item(self):
        return self.__item

    @property
    def value(self):
        return self.__value

    @property
    def user(self):
        return self.__user

    @property
    def repository(self):
        return self.__repository
