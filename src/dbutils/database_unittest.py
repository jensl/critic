def cursors():
    import api
    import dbutils

    class TestException(Exception):
        pass

    critic = api.critic.startSession(for_testing=True)

    # Create some playground tables.  We'll drop them later if all goes well,
    # but it doesn't really matter if we don't.
    with dbutils.Database.forTesting(critic) as db:
        db.cursor().execute(
            "CREATE TABLE playground1 ( x INTEGER PRIMARY KEY, y INTEGER )")
        db.cursor().execute(
            "CREATE TABLE playground2 ( x INTEGER PRIMARY KEY, y INTEGER )")
        db.commit()

    # Basic testing of read-only / updating cursors.
    with dbutils.Database.forTesting(critic) as db:
        ro_cursor = db.readonly_cursor()

        with db.updating_cursor("playground1") as cursor:
            cursor.executemany("INSERT INTO playground1 (x, y) VALUES (%s, %s)",
                               [(1, 1),
                                (2, 2),
                                (3, 3)])

        db.rollback()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 3

        try:
            with db.updating_cursor("playground1") as cursor:
                cursor.execute("INSERT INTO playground1 (x, y) VALUES (%s, %s)",
                               (4, 4))
                raise TestException
        except TestException:
            pass

        db.commit()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 3

        try:
            with db.updating_cursor("playground1") as cursor:
                cursor.execute("INSERT INTO playground2 (x, y) VALUES (%s, %s)",
                               (1, 1))
        except dbutils.InvalidCursorError as error:
            assert error.message == "invalid table for updating cursor: playground2"

        db.commit()
        ro_cursor.execute("SELECT x, y FROM playground2")
        assert len(list(ro_cursor)) == 0

        try:
            with db.updating_cursor("playground2") as cursor:
                cursor.execute("DELETE FROM playground1 WHERE x=1")
        except dbutils.InvalidCursorError as error:
            assert error.message == "invalid table for updating cursor: playground1"

        db.commit()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 3

        with db.updating_cursor("playground1") as cursor:
            cursor.execute("DELETE FROM playground1 WHERE x=1")

        db.rollback()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 2

        with db.updating_cursor("playground1") as cursor:
            cursor.execute("UPDATE playground1 SET y=-2 WHERE x=2")

        db.rollback()
        ro_cursor.execute("SELECT y FROM playground1 WHERE x=2")
        assert ro_cursor.fetchone()[0] == -2

        with db.updating_cursor("playground1", "playground2") as cursor1:
            with db.updating_cursor("playground1") as cursor2:
                cursor2.execute("UPDATE playground1 SET y=-2 WHERE x=2")
                try:
                    cursor2.execute("UPDATE playground2 SET y=-2 WHERE x=2")
                    assert False
                except dbutils.InvalidCursorError as error:
                    assert error.message == "invalid table for updating cursor: playground2"
            cursor2.execute("UPDATE playground1 SET y=1 WHERE x=10")
            cursor2.execute("UPDATE playground2 SET y=1 WHERE x=10")

        with db.updating_cursor("playground1") as cursor:
            try:
                with db.updating_cursor("playground2"):
                    assert False
            except dbutils.InvalidCursorError as error:
                assert error.message == "invalid table(s) for nested updating cursor: playground2"

        stored_cursor = None
        with db.updating_cursor("playground1") as cursor:
            stored_cursor = cursor
        try:
            stored_cursor.execute("UPDATE playground1 SET y=-3 WHERE x=3")
        except dbutils.InvalidCursorError as error:
            assert error.message == "disabled updating cursor used"

        db.commit()
        ro_cursor.execute("SELECT y FROM playground1 WHERE x=3")
        assert ro_cursor.fetchone()[0] == 3

        try:
            with db.updating_cursor("playground1") as cursor:
                cursor.execute("DROP TABLE playground1")
        except dbutils.InvalidCursorError as error:
            assert error.message == "unrecognized query: DROP", error.message

        try:
            with db.updating_cursor("playground1") as cursor:
                cursor.execute("DELETE FROM playground1")
                db.commit()
        except dbutils.InvalidCursorError as error:
            assert error.message == "manual commit when using updating cursor", error.message

        db.commit()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 2

    # Test mixing of unsafe cursor and updating cursor.
    with dbutils.Database.forTesting(critic) as db:
        ro_cursor = db.readonly_cursor()
        unsafe_cursor = db.cursor()

        with db.updating_cursor("playground1") as cursor:
            cursor.execute("DELETE FROM playground1")
            cursor.executemany("INSERT INTO playground1 (x, y) VALUES (%s, %s)",
                               [(1, 1),
                                (2, 2),
                                (3, 3)])

        db.rollback()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 3

        # Can't create an updating cursor after executing an updating query
        # using an unsafe cursor.
        try:
            unsafe_cursor.execute("DELETE FROM playground1")
            with db.updating_cursor("playground1") as cursor:
                assert False
        except dbutils.InvalidCursorError as error:
            assert error.message == "mixed unsafe and updating cursors"

        db.rollback()

        # Can't commit an updating cursor after executing an updating query
        # using an unsafe cursor.
        try:
            with db.updating_cursor("playground1") as cursor:
                cursor.execute("INSERT INTO playground1 (x, y) VALUES (%s, %s)",
                               (4, 4))
                unsafe_cursor.execute("DELETE FROM playground1")
        except dbutils.InvalidCursorError as error:
            assert error.message == "mixed unsafe and updating cursors"

        db.commit()
        ro_cursor.execute("SELECT x, y FROM playground1")
        assert len(list(ro_cursor)) == 3

        # If the transaction is committed or rolled back after execution of
        # updating query using unsafe cursor, then use of updating cursor is
        # fine.
        unsafe_cursor.execute("DELETE FROM playground1")
        db.rollback()
        with db.updating_cursor("playground1") as cursor:
            cursor.execute("UPDATE playground1 SET y=-2 WHERE x=2")

        db.rollback()
        ro_cursor.execute("SELECT y FROM playground1")
        assert set(y for (y,) in ro_cursor) == set([1, -2, 3])

        # If the transaction is committed or rolled back after execution of
        # updating query using unsafe cursor, then use of updating cursor is
        # fine.
        unsafe_cursor.execute("UPDATE playground1 SET y=-1 WHERE x=1")
        db.commit()
        with db.updating_cursor("playground1") as cursor:
            cursor.execute("UPDATE playground1 SET y=-3 WHERE x=3")

        db.rollback()
        ro_cursor.execute("SELECT y FROM playground1")
        assert set(y for (y,) in ro_cursor) == set([-1, -2, -3])

    # Drop the playground table.
    with dbutils.Database.forTesting(critic) as db:
        db.cursor().execute("DROP TABLE playground1")
        db.cursor().execute("DROP TABLE playground2")
        db.commit()

    print "cursors: ok"

def analyzeQuery():
    import dbutils

    # Trivial cases.
    assert dbutils.Database.analyzeQuery(
        "SELECT foo FROM bar WHERE fie") == ("SELECT", None)
    assert dbutils.Database.analyzeQuery(
        "UPDATE foo SET bar=10 WHERE fie") == ("UPDATE", "foo")
    assert dbutils.Database.analyzeQuery(
        "INSERT INTO foo (bar) VALUES (10)") == ("INSERT", "foo")
    assert dbutils.Database.analyzeQuery(
        "DELETE FROM foo WHERE bar AND fie") == ("DELETE", "foo")

    # Something more complex.
    assert dbutils.Database.analyzeQuery(
        """WITH allpaths (path) AS (VALUES (%s)),
                missingpaths (path) AS (SELECT allpaths.path
                                          FROM allpaths
                               LEFT OUTER JOIN files ON (MD5(files.path)=MD5(allpaths.path))
                                         WHERE files.path IS NULL)
           INSERT INTO files (path)
                SELECT path
                  FROM missingpaths""") == ("INSERT", "files")

    print "analyzeQuery: ok"
