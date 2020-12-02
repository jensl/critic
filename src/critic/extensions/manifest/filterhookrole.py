from typing import Optional

from critic import dbaccess
from .role import Role


class FilterHookRole(Role, role_type="filterhook"):
    name = "FilterHook"
    table_names = {"extensionfilterhookroles"}

    def __init__(self, *, name: str, title: str, data_description: Optional[str]):
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

    # def check_specific(self, manifest: Manifest) -> None:
    #     Role.check(self)
    #     if not re.match("^[a-z0-9_]+$", self.name, re.IGNORECASE):
    #         raise ManifestError(
    #             f"{self.location}: manifest error: invalid filter hook name: "
    #             "should contain only ASCII letters and numbers "
    #             "and underscores"
    #         )

    async def install_specific(
        self, cursor: dbaccess.TransactionCursor, role_id: int
    ) -> None:
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
