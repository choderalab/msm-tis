'''

@author: JD Chodera
@author: JH Prinz
'''

import copy

import numpy as np
import mdtraj as md

#THIS SHOULD NOT BE NECESSARY! SEE XYZ BELOW
import simtk.unit as u 


#=============================================================================
# SIMULATION CONFIGURATION
#=============================================================================

class Configuration(object):

    """
    Simulation configuration. Only Coordinates, the associated boxvectors
    and the potential_energy
    """

    # Class variables to store the global storage and the system context
    # describing the system to be safed as configuration_indices
    engine = None
    load_lazy = True

    def __init__(self, coordinates=None, box_vectors=None,
                 potential_energy=None, topology=None):
        """
        Create a simulation configuration from either an OpenMM context or
        individually-specified components.

        Parameters
        ----------
        coordinates : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic coordinates (default: None)
        box_vectors : periodic box vectors (default: None)
            the periodic box vectors at current timestep (defautl: None)
        potential_energy : simtk.unit.Quantity of units energy/mole
            potential energy at current timestep (default: None)

        Attributes
        ----------
        coordinates : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic coordinates
        box_vectors : periodic box vectors
            the periodic box vectors
        potential_energy : simtk.unit.Quantity of units energy/mole
            potential energy
        idx : dict( Storage() : int )
            dict for storing the used index per storage
        topology : mdtraj.Topology()
            a reference to the used topology. This is necessary to allow
            export to mdtraj objects
        """

        self.coordinates = None
        self.box_vectors = None
        self.potential_energy = None
        self.topology = None

        if topology is not None:
            self.topology = topology

        if coordinates is not None: 
            self.coordinates = copy.deepcopy(coordinates)
        if box_vectors is not None: 
            self.box_vectors = copy.deepcopy(box_vectors)
        if potential_energy is not None: 
            self.potential_energy = copy.deepcopy(potential_energy)

        if self.coordinates is not None:
            # Check for nans in coordinates, and raise an exception if
            # something is wrong.
            if np.any(np.isnan(self.coordinates)):
                raise ValueError("Some coordinates became 'nan'; simulation is unstable or buggy.")

        return

    def forget(self):
        """
        Will remove the stored coordinates from memory if they are stored in
        a file to save memory.  Once the coordinates are accessed they are
        reloaded automatically
        """

        if Configuration.load_lazy and hasattr(self, '_loaded_from'):
            self.coordinates = None
            self.box_vectors = None
            self.potential_energy = None

    #=========================================================================
    # Comparison functions
    #=========================================================================

    def __eq__(self, other):
        if self is other:
            return True

        # This is not good since this code requires knowledge about storage
        # I remove it since it is not used yet anyway
        # If we want to figure out if two Snapshots are loaded from two different
        # instances of the storage we should put this logic into storages

#        for storage in self.idx:
#            if storage in other.idx and other.idx[storage] == self.idx[storage]:
#                return True

        return False


    @property
    def n_atoms(self):
        '''
        Returns the number of atoms in the configuration
        '''
        return self.coordinates.shape[0]

    #=========================================================================
    # Utility functions
    #=========================================================================

    def copy(self, subset=None):
        """
        Returns a deep copy of the instance itself. If this object is saved
        it will not be stored as a separate object and consume additional
        memory. Should be avoided!

        Returns
        -------
        Configuration()
            the deep copy
        """

        if subset is None:
            this = Configuration(coordinates=self.coordinates, box_vectors=self.box_vectors, potential_energy=self.potential_energy, topology=self.topology)
        else:
            new_coordinates = self.coordinates[subset,:]
            new_topology = self.topology.subset(subset)
            # TODO: Keep old potential_energy? Is not correct but might be useful. Boxvectors are fine!
            this = Configuration(coordinates=new_coordinates, box_vectors=self.box_vectors, potential_energy=self.potential_energy, topology=new_topology)

        return this

    def md(self):
        '''
        Returns a mdtraj.Trajectory() object that contains only one frame

        Returns
        -------
        mdtraj.Tractory
            the actual trajectory object. Can be used with all functions from mdtraj

        Notes
        -----
        Rather slow since the topology has to be made each time. Try to avoid it
        '''

        n_atoms = self.n_atoms

        output = np.zeros([1, n_atoms, 3], np.float32)
        output[0,:,:] = self.coordinates

        return md.Trajectory(output, self.topology)

#=============================================================================
# SIMULATION MOMENTUM / VELOCITY
#=============================================================================

class Momentum(object):
    """
    Simulation momentum. Contains only velocities of all atoms and
    associated kinetic energies
    """
    
    # Class variables to store the global storage and the system context
    # describing the system to be safed as momentums
    engine = None
    load_lazy = True

    def __init__(self, velocities=None, kinetic_energy=None):
        """
        Create a simulation momentum from either an OpenMM context or
        individually-specified components.

        Parameters
        ----------
        velocities : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic velocities (default: None)
        kinetic_energy : simtk.unit.Quantity of units energy/mole
            kinetic energy at current timestep (default: None)
            
        Attributes
        ----------
        velocities : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic velocities
        kinetic_energy : simtk.unit.Quantity of units energy/mole
            kinetic energy
        idx : dict( Storage() : int )
            dict for storing the used index per storage
        """
        
        self.velocities = None
        self.kinetic_energy = None

        if velocities is not None: 
            self.velocities = copy.deepcopy(velocities)
        if kinetic_energy is not None: 
            self.kinetic_energy = copy.deepcopy(kinetic_energy)

        return

    def forget(self):
        """
        Will remove the stored Momentum data from memory if they are stored
        in a file to save memory.  Once the coordinates are accessed they
        are reloaded automatically
        """

        if Momentum.load_lazy and hasattr(self, '_loaded_store') > 0:
            self.velocities = None
            self.kinetic_energy = None

    @property
    def n_atoms(self):
        '''
        Returns the number of atoms in the momentum
        '''   
        return self.velocities.shape[0]

    #=========================================================================
    # Utility functions
    #=========================================================================

    def copy(self, subset=None, reversed=False):
        """
        Returns a deep copy of the instance itself. If this object will not
        be saved as a separate object and consumes additional memory. It is
        used to construct a reversed copy that can be stored or used to
        start a simulation. If the momentum is shallow it will be loaded for
        the copy

        Returns
        -------
        Momentum()
            the deep copy
        """


        if subset is None:
            new_velocities = self.velocities
        else:
            new_velocities = self.velocities[subset,:]
            # TODO: Keep old kinetic_energy? Is not correct but might be useful.

        if reversed:
            # Note the v *= -1.0 would be in place for numpy arrays. This here makes a copy!
            new_velocities = -1.0 * new_velocities

        this = Momentum(velocities=new_velocities, kinetic_energy=self.kinetic_energy)

        return this

    def reversed_copy(self, subset=None):
        """
        Create a copy and flips the velocities and erases the stored indices.
        If stores is will be treated as a new Momentum instance.
        Should be avoided.

        Returns
        -------
        Momentum()
            the deep copy with reversed velocities.
        """
        return self.copy(subset=subset, reversed=reversed)




#=============================================================================
# SIMULATION SNAPSHOT (COMPLETE FRAME WITH COORDINATES AND VELOCITIES)
#=============================================================================

def has(attr):
    def _has(func):
        def inner(self, *args, **kwargs):
            if hasattr(self, attr):
                return func(self, *args, **kwargs)
            else:
                return None
        return inner
    return _has



class Snapshot(object):
    """
    Simulation snapshot. Contains references to a configuration and momentum
    """
    
    # Class variables to store the global storage and the system context
    # describing the system to be saved as snapshots
    # Hopefully these class member variables will not be needed any longer
    engine = None

    def __init__(self, coordinates=None, velocities=None, box_vectors=None,
                 potential_energy=None, kinetic_energy=None, topology=None,
                 configuration=None, momentum=None, reversed=False):
        """
        Create a simulation snapshot. Initialization happens primarily in
        one of two ways:
            1. Specify `Configuration` and `Momentum` objects
            2. Specify the things which make up `Configuration` and
               `Momentum` objects, i.e., coordinates, velocities, box
               vectors, etc.
        If you want to obtain a snapshot from a currently-running MD engine,
        use that engine's .current_snapshot property.

        Parameters
        ----------
        coordinates : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic coordinates (default: None)
        velocities : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic velocities (default: None)
        box_vectors : periodic box vectors (default: None)
            the periodic box vectors at current timestep (defautl: None)
        potential_energy : simtk.unit.Quantity of units energy/mole
            potential energy at current timestep (default: None)
        kinetic_energy : simtk.unit.Quantity of units energy/mole
            kinetic energy at current timestep (default: None)
            
        Attributes
        ----------
        coordinates : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic coordinates
        velocities : simtk.unit.Quantity wrapping Nx3 np array of dimension length
            atomic velocities
        box_vectors : periodic box vectors
            the periodic box vectors 
        potential_energy : simtk.unit.Quantity of units energy/mole
            potential energy
        kinetic_energy : simtk.unit.Quantity of units energy/mole
            kinetic energy
        idx : dict( Storage() : int )
            dict for storing the used index per storage
        """
        
        if configuration is None:
            self.configuration = Configuration()
        else:
            self.configuration = configuration
        if momentum is None:
            self.momentum = Momentum()
        else:
            self.momentum = momentum

        if topology is not None:
            self.configuration.topology = topology

        self.reversed = reversed

        if coordinates is not None: 
            self.configuration.coordinates = copy.deepcopy(coordinates)
        if velocities is not None: 
            self.momentum.velocities = copy.deepcopy(velocities)
        if box_vectors is not None: 
            self.configuration.box_vectors = copy.deepcopy(box_vectors)
        if potential_energy is not None: 
            self.configuration.potential_energy = copy.deepcopy(potential_energy)
        if kinetic_energy is not None: 
            self.momentum.kinetic_energy = copy.deepcopy(kinetic_energy)

        # TODO: consider whether it is cleaner to move this logic into the
        # main allocation process instead of fixing things after the fact
        config = self.configuration
        if config.coordinates is None and config.box_vectors is None and config.potential_energy is None:
            self.configuration = None
        moment = self.momentum
        if moment.velocities is None and moment.kinetic_energy is None:
            self.momentum = None


        if self.configuration is not None and self.configuration.coordinates is not None:
            # Check for nans in coordinates, and raise an exception if
            # something is wrong.
            if np.any(np.isnan(self.configuration.coordinates)):
                raise ValueError("Some coordinates became 'nan'; simulation is unstable or buggy.")
                
        pass

    @property
    @has('configuration')
    def topology(self):
        """
        The mdtraj.Topology store in the configuration if present.
        """
        return self.configuration.topology

    @property
    @has('configuration')
    def coordinates(self):
        """
        The coordinates in the configuration
        """
        return self.configuration.coordinates

    @property
    @has('configuration')
    def xyz(self):
        """
        Coordinates without dimensions.

        SERIOUS PROBLEM: whether .coordinates returns a u.Quantity or jut
        numpy array depending on situation (at least for ToyDynamics). This
        is bad.
        """
        coord = self.configuration.coordinates
        if type(coord) is u.Quantity:
            return coord._value
        else:
            return coord

    @property
    @has('momentum')
    def velocities(self):
        """
        The velocities in the configuration. If the snapshot is reversed a
        copy of the original (unreversed) velocities is made which is then
        returned
        """
        if self.reversed:
            return -1.0 * self.momentum.velocities
        else:
            return self.momentum.velocities
    
    @property
    @has('configuration')
    def box_vectors(self):
        """
        The box_vectors in the configuration
        """
        if self.configuration is not None:
            return self.configuration.box_vectors
        else:
            return None
    
    @property
    @has('configuration')
    def potential_energy(self):
        """
        The potential_energy in the configuration
        """
        if self.configuration is not None:
            return self.configuration.potential_energy
        else:
            return None
    
    @property
    @has('momentum')
    def kinetic_energy(self):
        """
        The kinetic_energy in the momentum
        """
        if self.momentum is not None:
            return self.momentum.kinetic_energy
        else:
            return None
    
    @property
    @has('configuration')
    def n_atoms(self):
        '''
        The number of atoms in the snapshot
        '''
        if self.configuration is not None:
            return self.coordinates.shape[0]
        else:
            return None

    @property
    @has('configuration')
    @has('momentum')
    def total_energy(self):
        '''
        The total energy (sum of potential and kinetic) of the snapshot
        '''   
        return self.kinetic_energy + self.potential_energy
    
    #==========================================================================
    # Utility functions
    #==========================================================================

    def copy(self):
        """
        Returns a shallow copy of the instance itself. The contained
        configuration and momenta are not copied.

        Returns
        -------
        Snapshot()
            the deep copy
        """
        this = Snapshot(configuration=self.configuration, momentum=self.momentum, reversed=self.reversed)
        return this
    
    def reversed_copy(self):
        """
        Returns a shallow reversed copy of the instance itself. The
        contained configuration and momenta are not copied and the momenta
        are marked reversed.

        Returns
        -------
        Snapshot()
            the deep copy
        """

        return self.copy().reverse()

    def reverse(self):
        """
        Reversed the momenta. This only flips a boolean and marks the given
        snapshot are reversed. This is fast and should be used instead of
        read velocity inversion.
        """
        # TODO: reversed=>is_reversed to avoid confusion w/ built-in reversed
        self.reversed = not self.reversed
        return self
    
    @has('configuration')
    def md(self):
        '''
        Returns a mdtraj Trajectory object that contains only one frame
        
        Notes
        -----        
        Rather slow since the topology has to be made each time. Try to avoid it
        '''        
        return self.configuration.md()

    def subset(self, subset):
        """
        Return a deep copy of the snapshot with reduced set of coordinates. Takes also care
        of adjusting the topology.

        Notes
        -----
        So far the potential and kinetic energies are copied and are thus false but still useful!?!
        """

        this = Snapshot(configuration=self.configuration.copy(subset), momentum=self.momentum.copy(subset), reversed=self.reversed)
        return this
