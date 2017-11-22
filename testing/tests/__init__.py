def expect_system_mail(subject, body=None):
    system_mail = mailbox.pop(testing.mailbox.ToRecipient("system@example.org"))
    testing.expect.check(subject, system_mail.headers["subject"][0]["value"])
    if body is not None:
        testing.expect.check(body.splitlines(), system_mail.lines)


def partial_json(expected=None, **keys):
    """JSON expected value where all (nested) objects accept additional keys"""
    if expected is None:
        expected = {}
    expected.update(keys)

    def inner(value):
        if isinstance(value, dict):
            value = {key: inner(nested) for key, nested in value.items()}
            value["*"] = "*"
        elif isinstance(value, list):
            value = [inner(nested) for nested in value]
        return value

    return inner(expected)


def unordered_list(*, key="id", expected, **default_attrs):
    def key_from_value(value):
        if isinstance(key, tuple):
            return tuple(value[k] for k in key)
        return value[key]

    def expanded(v, k):
        if isinstance(key, tuple):
            v.update({n: k[i] for i, n in enumerate(key)})
        else:
            v[key] = k
        for defk, defv in default_attrs.items():
            v.setdefault(defk, defv)
        return v

    expected = {k: expanded(v, k) for k, v in expected.items()}

    def check(path, actual, check):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {actual!r}"]
        errors = []
        for index, v in enumerate(actual):
            if not isinstance(v, dict):
                errors.append(f"{path}[{index}]: expected dict, got {v!r}")
                continue
            try:
                k = key_from_value(v)
            except KeyError:
                errors.append(f"{path}[{index}]: does not have all expected keys")
                continue
            try:
                e = expected.pop(k)
            except KeyError:
                errors.append(f"{path}[{index}]: unexpected key: {k!r}")
                continue
            check(f"{path}[{index}]", e, v)
        return errors

    return check


def expected_error(*, title, message=None, code=None):
    expected_error = {"title": title}
    if message is not None:
        expected_error["message"] = message
    if code is not None:
        expected_error["code"] = code
    if message is None or code is None:
        expected_error["*"] = "*"
    return {"error": expected_error}
