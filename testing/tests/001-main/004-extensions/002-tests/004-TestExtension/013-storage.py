with frontend.signin("alice"):
    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.get('the key');" },
        expect={ "result": None })

    frontend.operation(
        "evaluate",
        data={ "source": "critic.storage.set('the key', 'the value');" },
        expect={ "result": None })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.get('the key');" },
        expect={ "result": "the value" })

    frontend.operation(
        "clearextensionstorage",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.get('the key');" },
        expect={ "result": None })
