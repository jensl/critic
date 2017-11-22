from .role import Role


class ProcessCommitsRole(Role, role_type="processcommits"):
    name = "ProcessCommits"
    table_names = {"extensionprocesscommitsroles"}

    async def install_specific(self, cursor, role_id):
        await cursor.execute(
            """INSERT INTO extensionprocesscommitsroles (role)
               VALUES ({role})""",
            role=role_id,
        )
