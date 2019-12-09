import pyflowgraph


def main():
    fg = pyflowgraph.build_from_file(file_path='examples/1.py')
    pyflowgraph.export_graph_image(fg)


if __name__ == '__main__':
    main()
