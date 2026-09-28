"""Read-only startup schema gate. Production startup never runs migrations."""
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

def verify_schema(connection, config_path='alembic.ini'):
    expected=set(ScriptDirectory.from_config(Config(config_path)).get_heads())
    actual=set(MigrationContext.configure(connection).get_current_heads())
    if actual != expected:
        raise RuntimeError('Database revision differs from this release; apply the reviewed migration separately before startup')
    return sorted(actual)

if __name__ == '__main__':
    from .database import engine
    with engine.connect() as connection:
        verify_schema(connection)
    print('Database revision matches release; no migration executed')
