import pytest


@pytest.fixture(scope="session")
def db(tmpdir_factory):
    fn = tmpdir_factory.mktemp("db")
    return fn
