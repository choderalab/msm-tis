"""
Quick test script to show how the automatic sleep optimization works.

Change the engine_sleep parameter to see different sleep times.
"""
import openpathsampling.engines as peng
import openpathsampling as paths
import numpy as np
import os
import logging


def build_engine(template):
    opts = {
        'n_frames_max' : 10000,
        # 'engine_sleep' : 20,
        'engine_sleep' : 500,
        'name_prefix' : "microtest",
        'engine_directory' : os.path.dirname(os.path.realpath(__file__))
    }
    engine = peng.ExternalEngine(opts, template)
    return engine

def run():
    template = peng.toy.Snapshot(coordinates=np.array([[0.0]]),
                                 velocities=np.array([[1.0]]))
    ensemble = paths.LengthEnsemble(20)
    engine = build_engine(template)
    logging.basicConfig(level=logging.INFO)
    engine.generate_forward(template, ensemble)

if __name__ == "__main__":
    run()
