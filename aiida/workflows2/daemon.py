# -*- coding: utf-8 -*-

from aiida.backends.utils import load_dbenv, is_dbenv_loaded

if not is_dbenv_loaded():
    load_dbenv()

import aiida.workflows2.defaults as defaults
from plum.engine.ticking import TickingEngine

__copyright__ = u"Copyright (c), 2015, ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE (Theory and Simulation of Materials (THEOS) and National Centre for Computational Design and Discovery of Novel Materials (NCCR MARVEL)), Switzerland and ROBERT BOSCH LLC, USA. All rights reserved."
__license__ = "MIT license, see LICENSE.txt file"
__version__ = "0.5.0"
__contributors__ = "Andrea Cepellotti, Giovanni Pizzi, Martin Uhrin"


def run_all_saved_processes(engine, storage):
    futures = []
    for cp in storage.load_all_checkpoints():
        futures.append(engine.run_from(cp))
    return futures


def tick_workflow_engine(registry=None, storage=None):
    if registry is None:
        registry = defaults.registry
    if storage is None:
        storage = defaults.storage

    engine = TickingEngine(defaults.factory, registry)
    run_all_saved_processes(engine, storage)
    work = engine.tick()
    engine.shutdown()
    return work != 0


if __name__ == "__main__":
    """
    A convenience method so that this module can be ran ticking the engine once.
    """
    from aiida.backends.utils import load_dbenv, is_dbenv_loaded

    if not is_dbenv_loaded():
        load_dbenv()

    tick_workflow_engine()
