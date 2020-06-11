[![JetBrains Research](https://jb.gg/badges/research.svg)](https://confluence.jetbrains.com/display/ALL/JetBrains+on+GitHub)

# Code Change Miner
A tool for mining graph-based change patterns in Python code.

## What it does
A **program dependence graph** is a way of representing the code by showing its data dependencies and control 
dependencies.

A **change graph** is a program dependence graph for the fragment of code changes (using the versions of code before 
and after the target change).

Similar code changes will have similar change graphs, which means that any versioned code can be mined for **patterns** 
in its changes. This tool does exactly that for Python code: it can build program dependence graphs, build change graphs 
for changed files, mine such change graphs from Git repositories by traversing their VCS history, and discover patterns 
in these change graphs.

This functionality can be used for empirical research of coding practices, as well as for mining the candidates for 
potential IDE inspections.

## Getting started
0. The tool requires Python 3.8+ to run.
1. Install the required dependencies:

    ```shell script
    pip3 install -r requirements.txt
    ```
    
2. If you want to use the tool for building change graphs or mining change graphs from the local repositories, you need 
to setup [GumTree](https://github.com/GumTreeDiff/gumtree). You can use the compiled version of GumTree 
(can be found in the [_external_](https://github.com/JetBrains-Research/code-change-miner/tree/master/external) 
directory), it is slightly modified and uses environment variables `GUMTREE_PYTHON_BIN` 
(python interpreter path for GumTree pyparser calls) and `GUMTREE_PYPARSER_PATH` (pyparser script path). 
Set them, for instance, as follows: 

     ```shell script
     GUMTREE_PYTHON_BIN=python3
     ```
     ```shell script
     GUMTREE_PYPARSER_PATH={project_dir}/external/pyparser.py
     ```
    
3. If you want to mine change graphs or patterns from the local repositories, create the settings file _settings.json_ 
based on [_conf/settings.json.example_](https://github.com/JetBrains-Research/code-change-miner/blob/master/conf/settings.json.example) 
and save it in the [same directory](https://github.com/JetBrains-Research/code-change-miner/tree/master/conf). 
You can find the description of individual settings 
in [_conf/help.md_](https://github.com/JetBrains-Research/code-change-miner/blob/master/conf/help.md).

## How to use
You can run any step of the pipeline by using the following simple command:
```shell script
python3 main.py <mode> <args>
```

The tool currently supports four operation modes:

1. `pfg` — build a program dependence graph from the Python source.

    Arguments:
    - `-i` — a path to the source file.
    - `-o` — a path to the output file. Two files will be created, a .dot file with a graph and a .pdf file 
    with its visualization.
    - `--no-closure` — **(optional)** if passed, no closure will be built for the graph.
    - `--show-deps` — **(optional)** if passed, edges with type _dep_ will be present in the graph, indicating 
    the dependence of the vertices on each other.
    - `--hide-op-kinds` — **(optional)** if passed, the types of operations will be hidden in the graph.
    - `--show-data-keys` — **(optional)** if passed, IDs of the variables will be present in the graph.
    
    Typical use:
    
    ```shell script
    python3 main.py pfg -i examples/src.py -o images/pfg.dot
    ```
    
2. `cg` — build a change graph from two source files (before and after change).

    Arguments:
    - `-s` — a path to the source file before changes.
    - `-d` — a path to the source file after changes.
    - `-o` — a path to the output file. Two files will be created, a .dot file with a graph and 
    a .pdf file with its visualization.
    
    Typical use:
    
    ```shell script
    python3 main.py cg -s examples/0_old.py -d examples/0_new.py -o images/cg.dot
    ```
    
3. `collect-cgs` — mine change graphs from local repositories.

    This mode takes no arguments, all the settings are located in the JSON file, see p. 3 of **Getting started**.
    
    Use:
    
    ```shell script
    python3 main.py collect-cgs
    ```
    
    The tool uses [pickle](https://docs.python.org/3/library/pickle.html) to save the data, so the output files 
    are serialized and can be only processed by pickle. Running the tool in the `patterns` mode 
    for detecting patterns within the mined change graphs will deserialize them automatically. 
    
4. `patterns` — search for patterns in the change graphs.

    This mode can be run in two ways: from the results of the previous step or from the source files. The settings 
    are located in the JSON file, see p. 3 of **Getting started**. If you want to look for patterns in the change graphs 
    obtained from running the tool in the `collect-sgs` mode, simply run:
    
    ```shell script
    python3 main.py patterns
    ```
    and the tool will find the input automatically. Alternatively, you can mine patterns directly from files 
    with the following arguments:

    - `-s` — a path to the source files before changes.
    - `-d` — a path to the source files after changes.
    - `--fake-mining` — **(optional)** if passed, no mining is carried out, the change graphs as a whole 
    are considered to be the patterns (used in debug).
    
    Typical use:
    
    ```shell script
    python3 main.py patterns -s examples/0_old.py examples/1_old.py -d examples/0_new.py examples/1_new.py
    ```
    
    Here, the files are automatically mapped (_0_old.py_ -> _0_new.py_, _1_old.py_ -> _1_new.py_), their change graphs 
    are built, and the patterns between them are mined. 
    
    In both usage scenarios, the `patterns` mode will produce results as shown in the picture below:
    
    <img src="https://sun9-47.userapi.com/c857320/v857320810/1b19c7/Sr42Lt0TfMU.jpg" alt="drawing" width="300"/>
    
    The patterns are organized by their size in nodes. In the output directory, a directory is created for each size, 
    in the example, the size is 17. In each of these directories we store the patterns, once again, as directories 
    with their ID in the name. In the example, 1379 is the ID of a pattern with size 17.
    
    Within each pattern, we store _details.html_ with its description and the listing of the pattern instances, 
    and the instances themselves. For each instance, there are three types of files: _sample{ID}_ is 
    the code of the instance (before and after the change), _fragment{ID}_ is the change graph of this specific sample, 
    and _graph{ID}_ is the larger change graph, from which this sample came from. You can also control 
    the specifics of the output by changing the settings file. _contents.html_ on every level of the structure provides
    a convenient navigation. To understand the structure better, you can browse an example 
    output in _survey_patterns.tar.gz_.
    
## Contacts
    
If you have any questions or suggestions, don't hesitate to open an issue or contact the developers 
at stardust.skg@gmail.com.
