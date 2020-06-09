[![JetBrains Research](https://jb.gg/badges/research.svg)](https://confluence.jetbrains.com/display/ALL/JetBrains+on+GitHub)

# Code Change Miner
A tool for mining graph-based change patterns in Python code.

## What it does
What is a graph? What is a change graph? Why do we need them? Why search for patterns?

## Getting started
0. The tool requires Python 3.8+ to run.
1. Install the required dependencies:

    ```shell script
    pip3 install -r requirements.txt
    ```
    
2. Create the settings file _settings.json_ based on _conf/settings.json.example_ and save it in the same directory. You can find the description of individual settings in _conf/help.md_ (**TODO**)
    
3. If you want to use the tool for building change graphs or mining change graphs from the local repositories, you need to setup [gumtree](https://github.com/GumTreeDiff/gumtree). Compiled gumtree is slightly modified and uses env variables `GUMTREE_PYTHON_BIN` (python interpreter path for gumtree pyparser calls) and `GUMTREE_PYPARSER_PATH` (pythonparser script path). Set them, for instance, as follows: 

     ```shell script
     GUMTREE_PYTHON_BIN=python3
     ```
     ```shell script
     GUMTREE_PYPARSER_PATH={project_dir}/external/pyparser.py
     ```
 
    Compiled gumtree and pyparser can be found at _external/_.

## How to use
You can run any step of the pipeline by using the following simple command:
```shell script
python main.py <mode> <args>
```

The tool currently supports four modes:
1. `pfg` — build a graph from the Python source.

    Possible arguments:
    - arg
    - arg
2. `cg` — build a change graph from two source files.

    Possible arguments:
    - arg
    - arg
3. `collect-cgs` — mine change graphs from local repositories.

    Possible arguments:
    - arg
    - arg
4. `patterns` — search for patterns in stored change graphs.

    Possible arguments:
    - arg
    - arg
