import api

class ConfigurationError(api.APIError):
    pass

class InvalidGroup(ConfigurationError):
    def __init__(self, name):
        super(ConfigurationError, self).__init__(
            "Invalid configuration group: %s" % name)

class InvalidKey(ConfigurationError):
    def __init__(self, group, name):
        super(ConfigurationError, self).__init__(
            "Invalid configuration key: %s::%s" % (group, name))

class WrongType(ConfigurationError):
    def __init__(self, group, name, read_as):
        super(ConfigurationError, self).__init__(
            "Wrong type: %s::%s (read as %s)" % (group, name, read_as))

def getValue(group, key):
    import configuration
    if not hasattr(configuration, group):
        raise InvalidGroup(group)
    module = getattr(configuration, group)
    if not hasattr(module, key):
        raise InvalidKey(group, key)
    return getattr(module, key)

def getBoolean(group, key):
    value = getValue(group, key)
    if not isinstance(value, bool):
        raise WrongType(group, key, "boolean")
    return value

def getInteger(group, key):
    value = getValue(group, key)
    if not isinstance(value, int):
        raise WrongType(group, key, "integer")
    return value

def getString(group, key):
    value = getValue(group, key)
    if not isinstance(value, basestring):
        raise WrongType(group, key, "string")
    return value
