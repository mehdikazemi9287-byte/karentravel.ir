from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.release_guard import verify_schema

def test_release_guard_never_upgrades_database(tmp_path):
    root=Path(__file__).resolve().parents[1]
    config=tmp_path/'alembic.ini';config.write_text('[alembic]\nscript_location = '+str(root/'alembic')+'\n')
    engine=create_engine('sqlite:///'+str(tmp_path/'revision.db'))
    with engine.begin() as connection:
        with pytest.raises(RuntimeError,match='revision differs'):verify_schema(connection,str(config))
        assert not connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
        connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)'))
        for head in ScriptDirectory.from_config(Config(str(config))).get_heads():connection.execute(text('INSERT INTO alembic_version VALUES (:head)'),{'head':head})
        assert verify_schema(connection,str(config))
        connection.execute(text("UPDATE alembic_version SET version_num='unknown-revision'"))
        with pytest.raises(RuntimeError,match='revision differs'):verify_schema(connection,str(config))
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar()=='unknown-revision'
