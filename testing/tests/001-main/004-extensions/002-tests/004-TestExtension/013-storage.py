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

    frontend.operation(
        "evaluate",
        data={ "source": """
critic.storage.set('a', '1');
critic.storage.set('b', '4');
critic.storage.set('aa', '2');
critic.storage.set('bb', '5');
critic.storage.set('aaa', '3');""" },
        expect={ "result": None })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.list();" },
        expect={ "result": ["a", "aa", "aaa", "b", "bb"] })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.list({ like: 'a%' });" },
        expect={ "result": ["a", "aa", "aaa"] })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.list({ like: 'aa%' });" },
        expect={ "result": ["aa", "aaa"] })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.list({ regexp: 'a+' });" },
        expect={ "result": ["a", "aa", "aaa"] })

    frontend.operation(
        "evaluate",
        data={ "source": "return critic.storage.list({ regexp: '[ab]*' });" },
        expect={ "result": ["a", "aa", "aaa", "b", "bb"] })
