A tool for graph-based change patterns mining in Python code.

Usage:<br>
python main.py \<mode> \<args>

Modes:<br>
pfg — build a graph from python src<br>
cg — build a change graph from two src files<br>
collect-cgs — mine change graphs from local repositories<br>
patterns — search for patterns in stored change graphs

Requirements:<br>
Python 3.8+

Setup:<br>
1. Create _settings.json_ from _conf/settings.json.example_ in the same directory.
2. Use <code>python -r requirements.txt</code> to install requirements.
3. If you want to use the tool in cg or collect-cgs modes, 
you need to setup [gumtree](https://github.com/GumTreeDiff/gumtree).
Compiled gumtree is slightly modified and uses env variables 
_GUMTREE_PYTHON_BIN_ (python interpreter path for gumtree pyparser calls) and 
_GUMTREE_PYPARSER_PATH_ (pythonparser script path). 
Set them, for instance, as follows: 
<code>GUMTREE_PYTHON_BIN=python3</code>, 
<code>GUMTREE_PYPARSER_PATH={project_dir}/external/pyparser.py</code>.
Compiled gumtree and pyparser can be found at _external/_.
