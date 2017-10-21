def basic():
    import api

    assert api.config.getBoolean("debug", "IS_TESTING") is True
    assert api.config.getBoolean("smtp", "USE_SSL") is False
    assert api.config.getInteger("smtp", "MAX_ATTEMPTS") == 10
    assert api.config.getString("base", "SYSTEM_IDENTITY") == "main"
    assert api.config.getValue("base", "REPOSITORY_URL_TYPES") == ["http"]

    try:
        api.config.getValue("invalid", "IRRELEVANT")
    except api.config.InvalidGroup as error:
        assert error.message == "Invalid configuration group: invalid"
    else:
        assert False

    try:
        api.config.getValue("base", "INVALID")
    except api.config.InvalidKey as error:
        assert error.message == "Invalid configuration key: base::INVALID"
    else:
        assert False

    try:
        api.config.getBoolean("base", "SYSTEM_USER_NAME")
    except api.config.WrongType as error:
        assert error.message == ("Wrong type: base::SYSTEM_USER_NAME "
                                 "(read as boolean)")
    else:
        assert False

    try:
        api.config.getInteger("base", "SYSTEM_USER_NAME")
    except api.config.WrongType as error:
        assert error.message == ("Wrong type: base::SYSTEM_USER_NAME "
                                 "(read as integer)")
    else:
        assert False

    try:
        api.config.getString("debug", "IS_TESTING")
    except api.config.WrongType as error:
        assert error.message == ("Wrong type: debug::IS_TESTING "
                                 "(read as string)")
    else:
        assert False

    print("basic: ok")
