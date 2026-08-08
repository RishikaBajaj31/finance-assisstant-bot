import pytest

from app.database.migrations.ensure_schema import ensure_schema


class FakeConn:
    def __init__(self, state: dict, actions: list[str]) -> None:
        self.state = state
        self.actions = actions

    async def run_sync(self, fn):
        self.actions.append("create_all")
        self.state["tables_created"] = True

    async def execute(self, statement):
        sql = str(statement)
        self.actions.append(sql)
        if "CREATE INDEX IF NOT EXISTS idx_memories_user_memory_key" in sql and not self.state["tables_created"]:
            raise AssertionError("CREATE INDEX ran before tables were created")


class FakeBegin:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeEngine:
    def __init__(self, state: dict, actions: list[str]) -> None:
        self.state = state
        self.actions = actions

    def begin(self):
        return FakeBegin(FakeConn(self.state, self.actions))


@pytest.mark.asyncio
async def test_ensure_schema_creates_tables_before_index_and_is_idempotent():
    state = {"tables_created": False}
    actions: list[str] = []
    engine = FakeEngine(state, actions)

    await ensure_schema(engine)
    await ensure_schema(engine)

    extension_calls = [idx for idx, action in enumerate(actions) if "CREATE EXTENSION IF NOT EXISTS vector" in action]
    create_all_indexes = [idx for idx, action in enumerate(actions) if action == "create_all"]
    memory_index_calls = [
        idx
        for idx, action in enumerate(actions)
        if "CREATE INDEX IF NOT EXISTS idx_memories_user_memory_key" in action
    ]

    assert len(extension_calls) == 2
    assert len(create_all_indexes) == 2
    assert len(memory_index_calls) == 2
    assert extension_calls[0] < create_all_indexes[0] < memory_index_calls[0]
    assert extension_calls[1] < create_all_indexes[1] < memory_index_calls[1]
