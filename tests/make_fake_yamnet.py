"""Builds a tiny stand-in for yamnet.onnx: same input/output names, always says 'Whoosh, swoosh, swish'."""
import csv
import os

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

HERE = os.path.dirname(os.path.abspath(__file__))


def build(path: str, winner: str = "Whoosh, swoosh, swish") -> str:
    names = [r["display_name"] for r in csv.DictReader(open(os.path.join(HERE, "..", "assets", "yamnet_class_map.csv"),
                                                            encoding="utf-8"))]
    scores = np.full((1, 521), 0.01, dtype=np.float32)
    scores[0, names.index("Music")] = 0.30
    scores[0, names.index(winner)] = 0.25
    nodes = [
        helper.make_node("ReduceSum", ["waveform"], ["s"], keepdims=1),
        helper.make_node("Mul", ["s", "zero"], ["z"]),
        helper.make_node("Add", ["base", "z"], ["output_0"]),
    ]
    g = helper.make_graph(nodes, "fake_yamnet",
                          [helper.make_tensor_value_info("waveform", TensorProto.FLOAT, [None])],
                          [helper.make_tensor_value_info("output_0", TensorProto.FLOAT, [None, 521])],
                          [numpy_helper.from_array(scores, "base"), numpy_helper.from_array(np.zeros(1, np.float32), "zero")])
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 8
    onnx.save(m, path)
    return path
