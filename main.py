from pyflowgraph import build_from_file
from changegraph import build_from_files
from pyflowgraph.visual import export_graph_image


def main():
    fg1 = build_from_file('examples/1.py')
    export_graph_image(fg1, 'G1')

    fg2 = build_from_file('examples/2.py')
    export_graph_image(fg2, 'G2')

    changegraph = build_from_files('examples/1.py', 'examples/2.py')
    export_graph_image(changegraph, 'CG')


if __name__ == '__main__':
    main()
