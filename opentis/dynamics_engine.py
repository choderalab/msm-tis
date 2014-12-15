'''
Created on 01.07.2014

@author JDC Chodera
@author: JH Prinz
'''

from opentis.trajectory import Trajectory
from opentis.ensemble import LengthEnsemble
import simtk.unit as u
from wrapper import storable

#=============================================================================
# SOURCE CONTROL
#=============================================================================

__version__ = "$Id: NoName.py 1 2014-07-06 07:47:29Z jprinz $"

#=============================================================================
# Multi-State Transition Interface Sampling
#=============================================================================

@storable
class DynamicsEngine(object):
    '''
    Class to wrap a simulation tool to store the context and rerun, needed
    parameters, storage, etc.
    
    Notes
    -----
    Should be considered an abstract class: only its subclasses can be
    instantiated.
    '''

    _default_options = {
        'n_atoms' : 0,
        'n_frames_max' : 0,
    }

    units = {
        'length' : u.Unit({}),
        'velocity' : u.Unit({}),
        'energy' : u.Unit({})
    }

    def __init__(self, filename=None, options=None, storage=None):
        '''
        Create an empty DynamicsEngine object
        
        Notes
        -----
        The purpose of an engine is to create trajectories and keep track
        of the results. The main method is 'generate' to create a
        trajectory, which is a list of snapshots and then can store the in
        the associated storage. In the initialization this storage is
        created as well as the related Trajectory and Snapshot classes are
        initialized.
        '''

        self.initialized = False
        self.running = dict()

        # if there has not been created a storage but the init of a derived
        # class make sure there is at least a member variable
        if not hasattr(self, 'storage'):
            self.storage = None

        if storage is not None:
            self.storage = storage

        # Trajectories need to know the engine as a hack to get the topology.
        # Better would be a link to the topology directly. This is needed to create
        # mdtraj.Trajectory() objects

        # TODO: Remove this and put the logic outside of the engine
        Trajectory.engine = self

        self._register_options(options)

        # TODO: switch this not needing slice; use can_append
        # this and n_atoms are the only general options we need and register
        if hasattr(self, 'n_frames_max'):
            self.max_length_stopper = LengthEnsemble(slice(0, self.n_frames_max + 1))

    def _register_options(self, options = None):
        """
        This will register all variables in the options dict as a member variable if
        they are present in either ther DynamicsEngine.default_options or this
        classes default_options, no multiple inheritance is supported!
        It will use values with the priority in the following order
        - DynamicsEngine.default_options
        - self.default_options
        - self.options (usually not used)
        - options (function parameter)
        Parameters are only registered if
        1. the variable name is present in the defaults
        2. the type matches the one in the defaults
        3. for variables with units also the units need to be compatible

        Parameters
        ----------
        options : dict of { str : value }
            A dictionary

        Notes
        -----
        Options are what is necessary to recreate the engine, but not runtime variables or independent
        variables like the actual initialization status, the runners or an attached storage.
        If there are non-default options present they will be ignored (no error thrown)
        """
        # start with default options from a dynamics engine
        my_options = {}
        okay_options = {}

        # self.default_options overrides default ones from DynamicsEngine
        for variable, value in self.default_options.iteritems():
            my_options[variable] = value

        if hasattr(self, 'options') and self.options is not None:
            # self.options overrides default ones
            for variable, value in self.options.iteritems():
                my_options[variable] = value

        if options is not None:
            # given options override even default and already stored ones
            for variable, value in options.iteritems():
                my_options[variable] = value

        if my_options is not None:
            for variable, default_value in self.default_options.iteritems():
                # create an empty member variable if not yet present
                if not hasattr(self, variable):
                    okay_options[variable] = None

                if variable in my_options:
                    if type(my_options[variable]) is type(default_value):
                        if type(my_options[variable]) is u.Unit:
                            if my_options[variable].unit.is_compatible(default_value):
                                okay_options[variable] = my_options[variable]
                            else:
                                raise ValueError('Unit of option "' + str(variable) + '" (' + str(my_options[variable].unit) + ') not compatible to "' + str(default_value.unit) + '"')

                        elif type(my_options[variable]) is list:
                            if type(my_options[variable][0]) is type(default_value[0]):
                                okay_options[variable] = my_options[variable]
                            else:
                                raise ValueError('List elements for option "' + str(variable) + '" must be of type "' + str(type(default_value[0])) + '"')
                        else:
                            okay_options[variable] = my_options[variable]
                    elif isinstance(type(my_options[variable]), type(default_value)):
                        okay_options[variable] = my_options[variable]
                    elif default_value is None:
                        okay_options[variable] = my_options[variable]
                    else:
                        raise ValueError('Type of option "' + str(variable) + '" (' + str(type(my_options[variable])) + ') is not "' + str(type(default_value)) + '"')

            self.options = okay_options

            for variable, value in okay_options.iteritems():
                setattr(self, variable, value)
        else:
            self.options = {}

    @property
    def default_options(self):
        default_options = {}
        default_options.update(DynamicsEngine._default_options)
        default_options.update(self._default_options)
        return default_options

    def start(self, snapshot=None):
        if snapshot is not None:
            self.current_snapshot = snapshot

    def stop(self, trajectory):
        """Nothing special needs to be done for direct-control simulations
        when you hit a stop condition."""
        pass

    def stoppers(self):
        """
        Return a set of runners that were set to stop in the last generation.

        Returns
        -------
        set
            a set of runners that caused the simulation to stop

        Example
        -------
        >>> if engine.max_length_stopper in engine.stoppers:
        >>>     print 'Max length was triggered'
        """
        return set([ runner for runner, result in self.running.iteritems() if not result])

    def generate(self, snapshot, running = None):
        r"""
        Generate a velocity Verlet trajectory consisting of ntau segments of
        tau_steps in between storage of Snapshots and randomization of
        velocities.

        Parameters
        ----------
        snapshot : Snapshot 
            initial coordinates; velocities will be assigned from
            Maxwell-Boltzmann distribution            
        running : list of function(Snapshot)
            callable function of a 'Snapshot' that returns True or False.
            If one of these returns False the simulation is stopped.

        Returns
        -------    
        trajectory : Trajectory
            generated trajectory of initial conditions, including initial
            coordinate set

        Notes
        -----
        Might add a return variable of the reason why the trajectory was
        aborted. Otherwise check the length and compare to max_frames
        """

        # Are we ready to rumble ?
        if self.initialized:
            
            self.current_snapshot = snapshot
            self.start()

            # Store initial state for each trajectory segment in trajectory.
            trajectory = Trajectory()
            trajectory.append(snapshot)
            
            frame = 0
            stop = False

            while stop == False:
                                
                # Do integrator x steps
                snapshot = self.generate_next_frame()
                frame += 1
                
                # Store snapshot and add it to the trajectory. Stores also
                # final frame the last time
                if self.storage is not None:
                    self.storage.snapshot.save(snapshot)
                trajectory.append(snapshot)
                
                # Check if we should stop. If not, continue simulation
                if running is not None:
                    for runner in running:
                        # note that even if one runner signals stop we evaluate
                        # all of them to access their results later
                        keep_running = runner(trajectory)
                        self.running[runner] = keep_running
                        stop = stop or not keep_running

                stop = stop or not self.max_length_stopper.can_append(trajectory)
                
            self.stop(trajectory)
            return trajectory
        else:
            raise RuntimeWarning("Can't generate from an uninitialized system!")

