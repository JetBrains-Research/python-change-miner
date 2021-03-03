import pytest

from deployment import set_all_environment_variables


@pytest.fixture(scope="session", autouse=True)
def prepare_for_tests():
    set_all_environment_variables()
