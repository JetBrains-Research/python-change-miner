from pyflowgraph.models import LinkType


class ExasFeature:
    """
    Features characterize code fragments
    Read more: "Accurate and Efficient Structural Characteristic Feature Extraction"
    """
    MAX_LENGTH = 4 * 2 - 1  # TODO: why?

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
            self.node_label_to_feature_id[node.label] = num + 1  # id skip is not critical, because of the same objects

    def get_id_by_label(self, label):
        return self.node_label_to_feature_id.get(label)

    def get_id_by_labels(self, labels):
        result = 0

        for num, label in enumerate(labels):
            if num % 2 == 0:
                s = self.node_label_to_feature_id.get(label)
            else:
                s = self.edge_label_to_feature_id.get(label, 0)
                s = s << 5  # TODO: are 2^4 exas types rly enough?
                result = result << 8

            result += s

        return result
