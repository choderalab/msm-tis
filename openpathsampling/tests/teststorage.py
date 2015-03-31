'''
@author David W.H. Swenson
'''
import os
from nose.tools import (assert_equal, assert_not_equal, assert_items_equal,
                        assert_almost_equal, raises)
from nose.plugins.skip import Skip, SkipTest
from test_helpers import (true_func, data_filename,
                          assert_equal_array_array,
                          assert_not_equal_array_array)

import numpy.testing as npt

from openpathsampling.openmm_engine import *
from openpathsampling.snapshot import Snapshot
from openpathsampling.snapshot import Momentum, Configuration

import simtk.unit as u
import time

def compare_snapshot(snapshot1, snapshot2):
    npt.assert_allclose(snapshot1.box_vectors, snapshot2.box_vectors, rtol=1e-7, atol=0)
    npt.assert_allclose(snapshot1.coordinates, snapshot2.coordinates, rtol=1e-7, atol=0)
    npt.assert_allclose(snapshot1.velocities, snapshot2.velocities, rtol=1e-7, atol=0)

    assert_equal(snapshot1.potential_energy, snapshot2.potential_energy)
    assert_equal(snapshot1.kinetic_energy, snapshot2.kinetic_energy)

def setUp():
    class Object():
        pass
    # Use the standard Alanine to generate snapshots to store for higher testing
    global this

    this = Object()

    this.options = {'temperature' : 300.0 * u.kelvin,
               'collision_rate' : 1.0 / u.picoseconds,
               'timestep' : 1.0 * u.femtoseconds,
               'nsteps_per_frame' : 1,
               'n_frames_max' : 5,
               'start_time' : time.time(),
               'fn_initial_pdb' : data_filename("ala_small_traj.pdb"),
               'platform' : 'fastest',
               'solute_indices' : range(22),
               'forcefield_solute' : 'amber96.xml',
               'forcefield_solvent' : 'tip3p.xml'
              }

    # create a template snapshot
    this.template_snapshot = paths.snapshot_from_pdb(data_filename("ala_small_traj.pdb"))

    # and an openmm engine
    this.engine = paths.OpenMMEngine(options=this.options, template=this.template_snapshot)
    this.engine.initialized = True

    # run a small trajectory of a few steps that can be used to save, etc...
    this.traj = this.engine.generate(this.template_snapshot, running=[paths.LengthEnsemble(2).can_append])

    this.filename = data_filename("storage_test.nc")
    this.filename_clone = data_filename("storage_test_clone.nc")



class testStorage(object):
    def setUp(self):
        # reuse objects everytime
        for key, value in this.__dict__.iteritems():
            setattr(self, key, value)

    def teardown(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)

        if os.path.isfile(self.filename_clone):
            os.remove(self.filename_clone)

    def test_create_template(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(data_filename("storage_test.nc")))
        store.close()

    def test_stored_topology(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(self.filename))
        store.close()

        store = Storage(filename=self.filename, mode='a')
        loaded_topology = store.template.topology

        # check if poth topologies have the same JSON string (this also tests the simplifier for topologies

        assert_equal(
            store.simplifier.to_json(self.template_snapshot.topology),
            store.simplifier.to_json(loaded_topology)
        )

        store.close()

        pass

    def test_write_load_str(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(self.filename))

        test_str = 'test_string'
        store.init_str('test_variable')
        store.write_str('test_variable', test_str)
        store.close()

        store2 = Storage(filename=self.filename, mode='a')
        loaded_str = store2.load_str('test_variable')

        assert(loaded_str == test_str)

        store2.close()
        pass

    def test_stored_template(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(self.filename))
        store.close()

        store = Storage(filename=self.filename, mode='a')
        loaded_template = store.template

        compare_snapshot(loaded_template, self.template_snapshot)

        store.close()
        pass

    def test_load_save(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(self.filename))

        copy = self.template_snapshot.copy()
        store.save(copy)

        store.close()

        store = Storage(filename=self.filename, mode='a')
        loaded_template = store.template

        compare_snapshot(loaded_template, self.template_snapshot)
        loaded_copy = store.load(Snapshot, 1)

        compare_snapshot(loaded_template, loaded_copy)

        store.close()
        pass


    def test_clone(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(self.filename))

        copy = self.template_snapshot.copy()
        store.save(copy)

        store.save(self.traj)
        store.clone(filename=self.filename_clone, subset = self.options['solute_indices'])

        # clone the storage and reduce the number of atoms to only solute

        store2 = Storage(filename=self.filename_clone, mode='a')

        # do some tests, if this is still the same data

        compare_snapshot(
            store2.snapshots.load(0),
            store.snapshots.load(0).subset(self.options['solute_indices'])
        )

        compare_snapshot(
            store2.snapshots.load(1),
            store.snapshots.load(1).subset(self.options['solute_indices'])
        )
        store.close()
        store2.close()

        pass

    def test_clone_empty(self):
        store = Storage(filename=self.filename, template=self.template_snapshot, mode='w')
        assert(os.path.isfile(self.filename))

        copy = self.template_snapshot.copy()
        store.save(copy)

        store.save(self.traj)
        store.clone_empty(filename=self.filename_clone)

        # clone the storage and reduce the number of atoms to only solute

        store2 = Storage(filename=self.filename_clone, mode='a')

        # do some tests, if this is still the same data

        compare_snapshot(
            store2.snapshots.load(0),
            store.snapshots.load(0)
        )

        assert_equal(store2.snapshots.count(), 1)
        assert_equal(store2.trajectories.count(), 0)

        store.close()
        store2.close()

        pass
