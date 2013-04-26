with frontend.signin("alice"):
    frontend.operation(
        "restrictions",
        data={},
        expect={ "database_connection": "PostgreSQL is not defined" })
