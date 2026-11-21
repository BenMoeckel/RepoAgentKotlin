from repo_agent.doc_meta_info import DocItem


def test_cyclic_graph_nodes_use_identity_for_membership_and_removal():
    left = DocItem(obj_name="callback")
    right = DocItem(obj_name="callback")
    left.father = left
    right.father = right
    left.children["callback"] = left
    right.children["callback"] = right
    left.reference_who.append(right)
    right.reference_who.append(left)
    assert left == left
    assert left != right
    assert left not in [right]
    nodes = [left, right]
    nodes.remove(right)
    assert len(nodes) == 1 and nodes[0] is left
