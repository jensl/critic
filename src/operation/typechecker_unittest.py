import copy
import json

def basic():
    import htmlutils

    from operation.basictypes import OperationError, OperationFailure
    from operation.typechecker import (
        Optional, TypeChecker, TypeCheckerContext, BooleanChecker,
        StringChecker, RestrictedString, SHA1, IntegerChecker,
        RestrictedInteger, PositiveInteger, NonNegativeInteger, ArrayChecker,
        EnumerationChecker, VariantChecker, DictionaryChecker)

    # Check TypeChecker.make()'s handling of basic types.
    assert type(TypeChecker.make(bool)) is BooleanChecker
    assert type(TypeChecker.make(str)) is StringChecker
    assert type(TypeChecker.make(int)) is IntegerChecker
    assert type(TypeChecker.make([bool])) is ArrayChecker
    assert type(TypeChecker.make(set(["foo", "bar"]))) is EnumerationChecker
    assert type(TypeChecker.make(set([bool, str, int]))) is VariantChecker
    assert type(TypeChecker.make({ "foo": bool })) is DictionaryChecker

    # Check TypeChecker.make()'s handling of TypeChecker sub-classes and
    # instances thereof.
    assert isinstance(TypeChecker.make(BooleanChecker), BooleanChecker)
    boolean_checker = BooleanChecker()
    assert TypeChecker.make(boolean_checker) is boolean_checker

    def check(checker, *values):
        checker = TypeChecker.make(checker)
        results = []
        for value in values:
            converted = checker(value, TypeCheckerContext(None, None, None))
            results.append(value if converted is None else converted)
        return results

    def should_match(checker, *values, **kwargs):
        results = check(checker, *values)
        if "result" in kwargs:
            expected_result = kwargs["result"]
            for result in results:
                assert result == expected_result, \
                    "%r != %r" % (result, expected_result)

    def should_not_match(checker, *values, **expected):
        for value in values:
            try:
                check(checker, copy.deepcopy(value))
            except (OperationError, OperationFailure) as error:
                error = json.loads(str(error))
                for key, value in expected.items():
                    if isinstance(value, str):
                        value = set([value])
                    assert error.get(key) in value, \
                        ("%s: %r not among %r" % (key, error.get(key), value))
            else:
                assert False, "checker allowed value incorrectly: %r" % value

    # Check some simple things that should be accepted.
    should_match(bool, True, False)
    should_match(str, "", "foo")
    should_match(int, -2**31, -1, 0, 1, 2**31)
    should_match([bool], [], [True, False])
    should_match([str], ["", "foo"])
    should_match([int], [-2**31, -1, 0, 1, 2**31])
    should_match(set(["foo", "bar"]), "foo", "bar")
    should_match(set([bool, str, int]),
                 True, False, "", "foo", -2**31, -1, 0, 1, 2**31)

    # Check some equally simple things that shouldn't be accepted.
    should_not_match(bool, 10, "foo",
                     error="invalid input: data is not a boolean")
    should_not_match(str, True, 10,
                     error="invalid input: data is not a string")
    should_not_match(int, True, "foo", 0.5,
                     error="invalid input: data is not an integer")
    should_not_match([bool], [True, 10], [False, "foo"],
                     error="invalid input: data[1] is not a boolean")
    should_not_match([str], ["", True], ["foo", 10],
                     error="invalid input: data[1] is not a string")
    should_not_match([int], [0, True], [10, "foo"],
                     error="invalid input: data[1] is not an integer")
    should_not_match(set(["foo", "bar"]), "fie",
                     error="invalid input: data is not valid")
    should_not_match(set(["foo", "bar"]), True, 10,
                     error="invalid input: data is not a string")
    should_not_match(set([bool, str, int]), [True], ["foo"], [10],
                     error="data is of invalid type")

    # Check some dictionary checkers.
    should_match({ "b": bool, "s": str, "i": int },
                 { "b": True, "s": "foo", "i": 10 })
    should_match({ "req": bool, "opt": Optional(bool) },
                 { "req": True, "opt": False },
                 { "req": False })
    should_not_match({ "b": bool }, { "b": "foo" }, { "b": 10 },
                     error="invalid input: data.b is not a boolean")
    should_not_match({ "b": bool }, { "i": 10 },
                     error="invalid input: data.b missing")
    should_not_match({ "b": bool }, { "b": True, "i": 10 },
                     error="invalid input: data.i was not used")
    should_not_match({ "b": Optional(bool) }, { "b": "foo" }, { "b": 10 },
                     error="invalid input: data.b is not a boolean")

    # Check suffixed variant checker in dictionary.
    id_or_name = VariantChecker({ "id": int, "name": str })
    should_match({ "thing": id_or_name },
                 { "thing": 10 },
                 { "thing_id": 10 },
                 result={ "thing": 10 })
    should_match({ "thing": id_or_name },
                 { "thing": "foo" },
                 { "thing_name": "foo" },
                 result={ "thing": "foo" })
    should_not_match({ "thing": id_or_name },
                     { "thing_id": "foo" },
                     error="invalid input: data.thing_id is not an integer")
    should_not_match({ "thing": id_or_name },
                     { "thing_name": 10 },
                     error="invalid input: data.thing_name is not a string")
    should_not_match({ "thing": id_or_name },
                     { "thing_id": 10,
                       "thing_name": "foo" },
                     error=("invalid input: data.thing_id was not used",
                            "invalid input: data.thing_name was not used"))

    # Check some RestrictedString types.
    should_match(RestrictedString, "", "foo")
    should_match(RestrictedString(minlength=0), "", "foo")
    should_match(RestrictedString(minlength=3), "foo")
    should_match(RestrictedString(maxlength=0), "")
    should_match(RestrictedString(maxlength=3), "", "foo")
    should_match(RestrictedString(minlength=0, maxlength=3), "", "foo")
    should_match(RestrictedString(allowed=lambda c: False), "")
    should_match(RestrictedString(allowed=lambda c: True), "", "foo")
    should_match(RestrictedString(allowed=lambda c: c in "foo"), "", "foo")
    should_not_match(RestrictedString(), True, 10,
                     error="invalid input: data is not a string")
    should_not_match(
        RestrictedString(minlength=1), "",
        code="paramtooshort:data",
        title="Invalid data",
        message="invalid input: data must be at least 1 characters long")
    should_not_match(
        RestrictedString(maxlength=2), "foo",
        code="paramtoolong:data",
        title="Invalid data",
        message="invalid input: data must be at most 2 characters long")
    should_not_match(
        RestrictedString(allowed=lambda c: False), "foo",
        code="paramcontainsillegalchar:data",
        title="Invalid data",
        message="invalid input: data may not contain the characters 'f', 'o'")
    should_not_match(
        RestrictedString(allowed=lambda c: False, ui_name="gazonk"), "foo",
        code="paramcontainsillegalchar:data",
        title="Invalid gazonk",
        message="invalid input: gazonk may not contain the characters 'f', 'o'")

    # Check SHA1.
    sha1 = "0123456789abcdefABCDEF0123456789abcdefAB"
    should_match(SHA1, *[sha1[:length] for length in range(4, 41)])
    should_not_match(SHA1, True, 10,
                     error="invalid input: data is not a string")
    for ch in range(0, 256):
        ch = chr(ch)
        if ch in sha1:
            continue
        should_not_match(
            SHA1, "012" + ch,
            message=htmlutils.htmlify(
                "invalid input: data may not contain the character %r" % ch))
    should_not_match(
        SHA1, "012",
        message="invalid input: data must be at least 4 characters long")
    should_not_match(
        SHA1, "0" * 41,
        message="invalid input: data must be at most 40 characters long")

    # Check some RestrictedInteger types.
    should_match(RestrictedInteger, -2**31, -1, 0, 1, 2**31)
    should_match(RestrictedInteger(minvalue=-2**31), -2**31, -1, 0, 1, 2**31)
    should_match(RestrictedInteger(minvalue=0), 0, 1, 2**31)
    should_match(RestrictedInteger(maxvalue=0), -2**31, -1, 0)
    should_match(RestrictedInteger(maxvalue=2**31), -2**31, -1, 0, 1, 2**31)
    should_match(RestrictedInteger(minvalue=0, maxvalue=0), 0)
    should_not_match(RestrictedInteger(), True, "foo",
                     error="invalid input: data is not an integer")
    should_not_match(RestrictedInteger(minvalue=0), -2**31, -1,
                     code="valuetoolow:data",
                     title="Invalid data parameter",
                     message="invalid input: data must be 0 or higher")
    should_not_match(RestrictedInteger(maxvalue=0), 1, 2**31,
                     code="valuetoohigh:data",
                     title="Invalid data parameter",
                     message="invalid input: data must be 0 or lower")
    should_not_match(RestrictedInteger(minvalue=1, ui_name="gazonk"), 0,
                     code="valuetoolow:data",
                     title="Invalid gazonk parameter",
                     message="invalid input: gazonk must be 1 or higher")

    # Check NonNegativeInteger.
    should_match(NonNegativeInteger, 0, 1, 2**31)
    should_not_match(NonNegativeInteger, True, "foo",
                     error="invalid input: data is not an integer")
    should_not_match(NonNegativeInteger, -2**31, -1,
                     code="valuetoolow:data",
                     title="Invalid data parameter",
                     message="invalid input: data must be 0 or higher")

    # Check PositiveInteger.
    should_match(PositiveInteger, 1, 2**31)
    should_not_match(PositiveInteger, True, "foo",
                     error="invalid input: data is not an integer")
    should_not_match(PositiveInteger, -2**31, -1, 0,
                     code="valuetoolow:data",
                     title="Invalid data parameter",
                     message="invalid input: data must be 1 or higher")

    print "basic: ok"
