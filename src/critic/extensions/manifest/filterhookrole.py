from . import ManifestError
from .role import Role


class FilterHookRole(Role, role_type="filterhook"):
    name = "FilterHook"
    table_names = {"extensionfilterhookroles"}

    def __init__(self, *, name, title, data_description):
        self.name = name
        self.title = title
        self.data_description = data_description

    def process(self, name, value, location):
        if Role.process(self, name, value, location):
            return True
        if name == "title":
            self.title = value
            return True
        if name == "datadescription":
            self.data_description = value
            return True
        return False

    def check(self):
        Role.check(self)
        if not re.match("^[a-z0-9_]+$", self.name, re.IGNORECASE):
            raise ManifestError(
                "%s: manifest error: invalid filter hook name: "
                "should contain only ASCII letters and numbers "
                "and underscores" % self.location
            )

    async def install(self, cursor, version_id):
        role_id = await Role.install(self, cursor, version_id)
        await cursor.execute(
            """INSERT INTO extensionfilterhookroles (
                        role, name, title, role_description,
                        data_description
                      )
               VALUES ({role}, {name}, {title}, {description},
                       {data_description})""",
            role=role_id,
            name=self.name,
            title=self.title,
            description=self.description,
            data_description=self.data_description,
        )
