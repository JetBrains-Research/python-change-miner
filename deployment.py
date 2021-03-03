import os

PROJECT_DIRECTORY = os.path.dirname(__file__)

PYTHON_BIN_ENV_VAR = "GUMTREE_PYTHON_BIN"
PYPARSER_ENV_VAR = "GUMTREE_PYPARSER_PATH"

PYTHON_BIN_VALUE = "python3"
PYPARSER_NAME = 'pythonparser_3.py'


def set_environment_variable(env_var, value):
    os.environ[env_var] = value


def set_all_environment_variables():
    set_environment_variable(PYTHON_BIN_ENV_VAR, PYTHON_BIN_VALUE)

    pyparser_path = os.path.join(PROJECT_DIRECTORY, 'external', PYPARSER_NAME)
    set_environment_variable(PYPARSER_ENV_VAR, pyparser_path)
