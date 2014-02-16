import weakref

import api
import dbutils

class Critic(object):
    def __init__(self, database):
        self.database = database
        self.__cache = {}

    def cached(self, cls, key, callback):
        wvd = self.__cache.setdefault(cls, weakref.WeakValueDictionary())
        try:
            value = wvd[key]
        except KeyError:
            value = wvd[key] = callback()
        assert isinstance(value, cls)
        return value

def startSession():
    return api.critic.Critic(Critic(dbutils.Database()))
