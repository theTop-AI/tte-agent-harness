import unittest

from tte_harness import dag


class DagTest(unittest.TestCase):
    def test_waves_group_independent_nodes(self):
        deps = {"a": [], "b": [], "c": ["a", "b"], "d": ["c"], "e": ["a"]}
        self.assertEqual(dag.waves(deps), [["a", "b"], ["c", "e"], ["d"]])

    def test_topological_respects_every_edge(self):
        deps = {"x": ["y"], "y": ["z"], "z": []}
        order = dag.topological(deps)
        self.assertEqual(order, ["z", "y", "x"])

    def test_cycle_is_found_and_named(self):
        deps = {"a": ["b"], "b": ["c"], "c": ["a"], "d": []}
        cycle = dag.find_cycle(deps)
        self.assertIsNotNone(cycle)
        self.assertEqual(cycle[0], cycle[-1])
        self.assertEqual(set(cycle), {"a", "b", "c"})

    def test_self_loop_is_a_cycle(self):
        self.assertEqual(dag.find_cycle({"a": ["a"]}), ["a", "a"])

    def test_acyclic_graph_has_no_cycle(self):
        self.assertIsNone(dag.find_cycle({"a": [], "b": ["a"], "c": ["a", "b"]}))

    def test_waves_refuse_cycles_and_unknown_nodes(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            dag.waves({"a": ["b"], "b": ["a"]})
        with self.assertRaisesRegex(ValueError, "unknown"):
            dag.waves({"a": ["ghost"]})


if __name__ == "__main__":
    unittest.main()
