import os


PROJECT_DIRECTORY = os.path.dirname(__file__)


def set_environment_variable(env_var, value):
    if os.getenv(env_var) is None:
        os.environ[env_var] = value


def set_all_environment_variables():
    PYTHON_BIN_ENV_VAR = "GUMTREE_PYTHON_BIN"
    PYTHON_BIN_VALUE = "python3"
    set_environment_variable(PYTHON_BIN_ENV_VAR, PYTHON_BIN_VALUE)

    PYPARSER_ENV_VAR = "GUMTREE_PYPARSER_PATH"
    pyparser_path = os.path.join(PROJECT_DIRECTORY, 'external', 'pythonparser_3.py')
    set_environment_variable(PYPARSER_ENV_VAR, pyparser_path)