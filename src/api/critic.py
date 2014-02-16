class Critic(object):
    def __init__(self, impl):
        self._impl = impl

    def getDatabase(self):
        return self._impl.database

    def getDatabaseCursor(self):
        return self._impl.database.cursor()

def startSession():
    import api.impl
    return api.impl.critic.startSession()
