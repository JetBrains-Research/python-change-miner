import json
import subprocess

import xml.etree.ElementTree as ET
from io import StringIO

import settings

# srcML should be installed and added to the PATH env variable
def parse(src):
    args = ['srcml', '--text=' + src, '--language', 'C', '--position']
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    result, _ = p.communicate()
    # print("++++++++++++= DEcode +++++++++++++++++++++++=")
    # print(result.decode('ascii'))
    # print("++++++++++++= DEcode +++++++++++++++++++++++=")

    return parse_xml(result) if result else None


def parse_xml(xml):
    # tree = ET.ElementTree(ET.fromstring(s))

    #  remove namespace prefixes
    it = ET.iterparse(StringIO(xml.decode('ascii')))
    for _, el in it:
        prefix, has_namespace, postfix = el.tag.partition('}')
        if has_namespace:
            el.tag = postfix  # strip all namespaces

        # Still need to remove namespace prefix from attrib dict
        # for el2 in el.attrib:
        #     prefixA, has_namespaceA, postfixA = el2.partition('}')
        #     if has_namespaceA:
        #         el.attrib[postfixA] = el.attrib.pop(el2)
    return it


class ASTVisitor:
    def __init__(self):
        ...

    def visit(self, node):
        """Get node type and visit a node."""
        method = 'visit_' + node.tag
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        for child in node:
            print("tag: ", child.tag)
            # print("attrib: ", child.attrib)
            # print("class name: ", child.__class__.__name__)
            self.visit(child)

    def visit_function(self, node):
        print("VISIT_FUNCTION")

    def visit_decl_stmt(self, node):
        print("VISIT_DECL_STMT")


class ASTTokens:
    def __init__(self, tree=False):
        ...
