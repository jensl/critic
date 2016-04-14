import sqlite3
import os
import re
import datetime

import installation

IntegrityError = sqlite3.IntegrityError
ProgrammingError = sqlite3.ProgrammingError
OperationalError = sqlite3.OperationalError

def convert_date(value):
    try:
        return datetime.datetime.fromtimestamp(int(value))
    except ValueError:
        return datetime.datetime.strptime(value, "%Y-%m-%d")

def convert_datetime(value):
    try:
        return datetime.datetime.fromtimestamp(int(value))
    except ValueError:
        return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

def convert_interval(value):
    try:
        return datetime.timedelta(seconds=int(value))
    except ValueError:
        return 0

def convert_boolean(value):
    return bool(int(value))

sqlite3.register_converter("DATE", convert_date)
sqlite3.register_converter("TIMESTAMP", convert_datetime)
sqlite3.register_converter("INTERVAL", convert_interval)
sqlite3.register_converter("BOOLEAN", convert_boolean)

def sqltokens(command):
    return re.findall(r"""\$\d+|!=|<>|<=|>=|'(?:''|[^'])*'|"(?:[^"])*"|\w+|[^\s]""", command)

def sqlcommands(filename):
    path = os.path.join(installation.root_dir, filename)
    script = []
    with open(path) as script_file:
        for line in script_file:
            fragment, _, comment = line.strip().partition("--")
            fragment = fragment.strip()
            if fragment:
                script.append(fragment)
    script = " ".join(script)
    return filter(None, map(str.strip, script.split(";")))

def replace(query, old, new):
    tokens = query if isinstance(query, list) else sqltokens(query)
    old = sqltokens(old)
    new = sqltokens(new)
    start = 0
    try:
        while True:
            for anchor_offset, anchor_token in enumerate(old):
                if anchor_token[0] != "$":
                    break
            offset = map(str.upper, tokens).index(old[anchor_offset].upper(), start) - anchor_offset
            data = {}
            for index in range(len(old)):
                if old[index][0] == "$":
                    data[old[index]] = tokens[offset + index]
                elif tokens[offset + index].upper() != old[index].upper():
                    start = offset + 1
                    break
            else:
                if data:
                    use_new = map(lambda token: data.get(token, token), new)
                else:
                    use_new = new
                tokens[offset:offset + len(old)] = use_new
                start = offset + len(use_new)
    except (IndexError, ValueError):
        return " ".join(tokens)

class Cursor(object):
    def __init__(self, connection):
        self.cursor = connection.cursor()

    def massage(self, query, parameters):
        self.flags = set()
        while "=ANY (%s)" in query:
            for index, parameter in enumerate(parameters):
                if isinstance(parameter, (list, set, tuple)):
                    query = query.replace("=ANY (%s)", " IN (%s)" % ", ".join(["?"] * len(parameter)), 1)
                    parameters[index:index + 1] = parameter
                    break
            else:
                assert False, "Failed to translate all occurrences of '=ANY (%s)' in query!"
        if query.endswith(" RETURNING id"):
            self.flags.add("returning_id")
            query = query[:-len(" RETURNING id")]
        tokens = sqltokens(query.replace("%s", "?"))
        replace(
            tokens,
            "EXTRACT ('epoch' FROM NOW() - $1)",
            "strftime('%s', 'now') - strftime('%s', $1)")
        replace(
            tokens,
            "EXTRACT ('epoch' FROM (MIN($1) - NOW()))",
            "strftime('%s', MIN($1)) - strftime('%s', 'now')")
        replace(tokens, "NOW()", "cast(strftime('%s', 'now') as integer)")
        replace(tokens, "TRUE", "1")
        replace(tokens, "FALSE", "0")
        replace(tokens, "'1 day'", str(24 * 60 * 60))
        replace(tokens, "next::text", "datetime(next, 'unixepoch')")
        replace(tokens, "commit", '"commit"')
        replace(tokens, "transaction", '"transaction"')
        replace(tokens, "MD5($1)", "$1")
        replace(tokens, "FETCH FIRST ROW ONLY", "")
        replace(tokens, "ASC NULLS FIRST", "ASC")
        replace(tokens, "DESC NULLS LAST", "DESC")
        replace(tokens, "chaincomments(commentchains.id)",
                """(SELECT COUNT(*) FROM comments
                                   WHERE chain=commentchains.id
                                     AND state='current')""")
        replace(tokens, "chainunread(commentchains.id, ?)",
                """(SELECT COUNT(*) FROM commentstoread
                                    JOIN comments ON (comments.id=commentstoread.comment)
                                   WHERE comments.chain=commentchains.id
                                     AND comments.state='current'
                                     AND commentstoread.uid=?)""")
        replace(tokens, "character_length(", "length(")
        replace(tokens, "FOR UPDATE NOWAIT", "")
        replace(tokens, "FOR UPDATE", "")
        replace(tokens, "~", "regexp")
        replace(tokens, "INTERVAL ?", "interval_seconds(?)")
        return " ".join(tokens)

    def execute(self, query, parameters=()):
        parameters = list(parameters)
        query = self.massage(query, parameters)
        try:
            self.cursor.execute(query, parameters)
        except sqlite3.OperationalError as error:
            raise Exception("Invalid query: %r %r" % (error.message, query))
        except sqlite3.InterfaceError as error:
            raise Exception("Invalid parameters: %r %r for %r" % (error.message, parameters, query))
        if "returning_id" in self.flags:
            self.cursor.execute("SELECT last_insert_rowid()")

    def executemany(self, query, parameters=()):
        parameters = list(parameters)
        query = self.massage(query, parameters)
        self.cursor.executemany(query, parameters)

    def fetchone(self):
        return self.cursor.fetchone()
    def fetchall(self):
        return self.cursor.fetchall()

    def __iter__(self):
        return iter(self.cursor)

def regexp(pattern, string):
    return re.search(pattern, string) is not None

def interval_seconds(string):
    match = re.match(r"(?:(-?\d+)\s+days)?\s*"
                     r"(?:(-?\d+)\s+hours)?\s*"
                     r"(?:(-?\d+)\s+minutes)?\s*"
                     r"(?:(-?\d+)\s+seconds)?",
                     string, re.I)
    days, hours, minutes, seconds = match.groups()
    result = 0
    if days is not None:
        result += 86400 * int(days)
    if hours is not None:
        result += 3600 * int(hours)
    if minutes is not None:
        result += 60 * int(minutes)
    if seconds is not None:
        result += int(seconds)
    return result

class Connection(object):
    def __init__(self, **parameters):
        self.connection = sqlite3.connect(
            detect_types=sqlite3.PARSE_DECLTYPES,
            **parameters)
        self.connection.create_function("regexp", 2, regexp)
        self.connection.create_function("interval_seconds", 1, interval_seconds)
        self.connection.text_factory = str
        # Foreign keys are disabled by default by SQLite; this enables them.
        # This is a safe-guard against incorrect inserts or updates, but most
        # importantly, it makes cascading deletes work, which we depend on.
        self.connection.execute("PRAGMA foreign_keys=ON")
    def cursor(self):
        return Cursor(self.connection)
    def commit(self):
        return self.connection.commit()
    def rollback(self):
        return self.connection.rollback()
    def close(self):
        return self.connection.close()

def connect(**parameters):
    return Connection(**parameters)

def import_schema(database_path, filenames, quiet=False, verbose=False):
    failed = False
    enumerations = {}
    commands = []
    db = sqlite3.connect(database_path)

    for filename in filenames:
        commands.extend(sqlcommands(filename))

    for command in commands:
        if command.startswith("SET "):
            # Skip SET; only used to control the output from psql.
            continue
        elif re.match(r"CREATE (?:UNIQUE )?INDEX \w+_(?:md5|gin)", command) \
                or re.match(r"CREATE (?:UNIQUE )?INDEX .* WHERE ", command):
            # Fancy index stuff not supported by sqlite.  Since they are
            # optional (sans performance requirements) we just skip them.
            continue
        elif command.startswith("CREATE TABLE ") \
                or command.startswith("CREATE INDEX ") \
                or command.startswith("CREATE UNIQUE INDEX ") \
                or command.startswith("CREATE VIEW ") \
                or command.startswith("INSERT INTO "):
            tokens = sqltokens(command)
            replace(tokens, "DEFAULT NOW()", "DEFAULT (cast(strftime('%s', 'now') as integer))")
            replace(tokens, "TRUE", "1")
            replace(tokens, "FALSE", "0")
            replace(tokens, "INTERVAL '0'", "0")
            replace(tokens, "SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY")
            replace(tokens, "commit", '"commit"')
            replace(tokens, "transaction", '"transaction"')
            for name, values in enumerations.items():
                replace(tokens, "$1 " + name, "$1 text check ($1 in (%s))" % ", ".join(values))
            command = " ".join(tokens)
        elif re.match(r"CREATE TYPE \w+ AS ENUM", command):
            tokens = sqltokens(command)
            name = tokens[2]
            values = filter(lambda token: re.match("'.*'$", token),
                            tokens[tokens.index("(") + 1:tokens.index(")")])
            enumerations[name] =  values
            continue
        elif command.startswith("ALTER TABLE "):
            # Used to add constraints after table creation, which sqlite doesn't
            # support.
            continue
        else:
            print "Unrecognized:", command
            failed = True

        if verbose:
            words = command.split()
            for word in words:
                if word.upper() != word:
                    print word
                    break
                print word,

        try:
            db.execute(command)
        except Exception as error:
            print "Failed:", command
            print "  " + str(error)
            failed = True

    if not failed:
        db.commit()

    return not failed
