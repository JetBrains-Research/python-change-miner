from pyflowgraph.models import LinkType

import sys

HALF_N = sys.maxsize // 2
N = HALF_N * 2


def normalize(value):
    return (value + HALF_N) % N - HALF_N


class ExasFeature:
    """
    Features characterize code fragments
    Read more: "Accurate and Efficient Structural Characteristic Feature Extraction"
    """
    MAX_LENGTH = 2 ** 3 - 1

    def __init__(self, nodes=None):
        self.node_label_to_feature_id = {}
        self.edge_label_to_feature_id = {
            LinkType.QUALIFIER: 0,
            LinkType.CONDITION: 1,
            LinkType.CONTROL: 2,
            LinkType.DEFINITION: 3,
            LinkType.MAP: 4,
            LinkType.PARAMETER: 5,
            LinkType.RECEIVER: 6,
            LinkType.REFERENCE: 7
        }

        if nodes is not None:
            self._bind_node_feature_ids(nodes)

    def _bind_node_feature_ids(self, nodes):
        for num, node in enumerate(nodes):
            self.node_label_to_feature_id[node.label] = num + 1  # some ids can be skipped

    def get_id_by_label(self, label):
        return self.node_label_to_feature_id.get(label)

    def get_id_by_labels(self, labels):
        result = 0

        for num, label in enumerate(labels):
            if num % 2 == 0:
                s = self.node_label_to_feature_id.get(label)
            else:
                s = self.edge_label_to_feature_id.get(label, 0)
                s = normalize(s << 5)  # 2^4 types
                result = normalize(result << 8)

            result = normalize(result + s)

        return result
