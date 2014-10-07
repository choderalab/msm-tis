###############################################################
#| CLASS Order Parameter
###############################################################

from msmbuilder.metrics import RMSD
from trajectory import Trajectory
from snapshot import Snapshot, Configuration
import numpy as np

class Cache(object):
    '''
    Initializes an OrderParameter object that is essentially a function that maps a frame (Snapshot) within a trajectory (Trajectory) to a number. 
    
    Parameters
    ----------
    fnc : index (int) -> value (float)
        the function used to generate the cache values for the specified index. In essence a list
        
    Attributes
    ----------
    cache : list
        A list object contained all cached values so far
    is_cached : set
        A set of indices that are cached for quick queries if an index is in the list or not.
        
    Notes
    -----        
    Does it have to be between 0 and 1?
    Do we want to save this in the netCDF?
    And if yes, do we want one big table for all OrderParameters or several ones. One for each. Second might be nicer.
    '''
    def __init__(self, fnc):

        # Name needed to eventually store to netCDF. This is not yet done
        self._eval = fnc

        # We will use a cache since we assume the snapshots objects, the OrderParameter Instance and the ID# of snapshots to be immutable
        self.cache = []
        self.is_cached = set()
            
    def __getslice__(self, *args, **kwargs):
        sl = slice(*args, **kwargs)
        return self[range(sl.stop)[sl]]
                
    @property
    def size(self):
        '''
        Returns the current size of the cache and thus the maximal index possibly in the cache.
        
        Returns
        -------
        size : int
            the length of the `cache` member variable
        '''
        return len(self.cache)
    
    def resize(self, size):
        '''
        Will increase the size of the cache to the specified size
        
        Parameters
        ----------
        size : int
            The new minimal size of the cache
        '''
        if size > self.size:
            self.cache.extend([0.0] * (size - self.size))
    
    def in_cache(self, indices):
        '''
        Find a subset of indices that are present in the cache
        
        Parameters
        ----------
        indices : list of int
            the initial list of indices to be tested
        
        Returns
        -------
        in_cache : list of int
            the subset of indices present in the cache
        '''
        return [idx for idx in indices if idx in self.is_cached]

    def not_in_cache(self, indices):
        '''
        Find a subset of indices that are NOT present in the cache
        
        Parameters
        ----------
        indices : list of int
            the initial list of indices to be tested
        
        Returns
        -------
        in_cache : list of int
            the subset of indices NOT present in the cache
        '''

        return [idx for idx in indices if idx not in self.is_cached]   
            
    def __getitem__(self, index):                
        # Allow for numpy style of selecting several indices using a list as index parameter
        if type(index) is list:
            max_idx = max(index) + 1
            self.resize(max_idx)
            no_cache = self.not_in_cache(index)                        
        else:
            self.resize(index + 1)
            no_cache = self.not_in_cache([index])

        # Add not yet cached data            
        if len(no_cache) > 0:
            result = self._eval(no_cache)
        
            for no, res in enumerate(result):
                self.cache[no_cache[no]] = res

            self.is_cached.update(no_cache)

        if type(index) is list:
            ret = [self.cache[idx] if idx > 0 else None for idx in index]                        
        else:                        
            ret = self.cache[index]  
                
        return ret
    
class SnapshotCache(Cache):
    '''
    A cache that is attached to snapshot indices store in the Snapshot storage

    Attributes
    ----------
    name : string
        A short and unique name to be used in storage

    Parameters
    ----------
    name : string
        A short and unique name to be used in storage

    '''
    def __init__(self, name, fnc):

        super(SnapshotCache, self).__init__(fnc = fnc)
        
        self.name = name

    def fill(self):
        '''
        Compute all distances for all snapshots to be used later using the cache. 
        
        Notes
        -----        
        Make sure that all snapshots are saved. Otherwise we cannot cache them!        
        '''

        self[1:Configuration.load_number() + 1]


    def _init_netcdf(self, storage):
        '''
        initializes the associated storage to save a specific order parameter in it
        
        Parameters
        ----------
        storage : Storage
            the storage to be associated to. Needs implementation
                    
        '''           
        # save associated storage in class variable for all Snapshot instances to access
        
#        ncgrp = storage.ncfile.createGroup('snapshot')
        
        self.storage = storage
        ncgrp = storage.ncfile
        
        # define dimensions used in snapshots
#        size_dimension = 'op_size_' + self.name
#        ncgrp.createDimension(size_dimension, self.size)                       # unlimited number of snapshots
        
        # define variables for OrderParameters
        var_name = 'order_parameter_' + self.name
        ncvar_order_parameter          = ncgrp.createVariable(var_name, 'f', ('snapshot', 'scalar'))

        # Define units for snapshot variables.
        setattr(ncvar_order_parameter, 'units', 'None')
        
        # Define long (human-readable) names for variables.
        setattr(ncvar_order_parameter,    "long_name", "orderparameter[snapshot][index] is the orderparameter of snapshot 'snapshot'.")
        
    def save(self):
        """
        Save the current state of the cache to the storage
        """
        
        ncfile = self.storage.ncfile

        # Make sure snapshots are stored and have an index and then add the snapshot index to the trajectory
        var_name = 'order_parameter_' + self.name
        indices = list(self.is_cached)
        ncfile.variables[var_name][:,0] = np.array(self.cache)
        ncfile.variables[var_name + '_idx'] = np.array(indices) 
        
        
    def load(self):
        '''
        Restores the cache from the storage        
        '''
        var_name = 'order_parameter_' + self.name
        self.cache = self.storage.ncfile.variables[var_name][:,0].astype(np.float).copy().as_list()
        self.is_cached = set(self.storage.ncfile.variables[var_name + '_idx'].astype(np.int).copy().as_list())  

class OrderParameter(object):
    '''
    Initializes an OrderParameter object that is essentially a function that maps a frame (Snapshot) within a trajectory (Trajectory) to a number. 
    
    Parameters
    ----------
    name : string
        A descriptive name of the orderparameter. It is used in the string representation.

    Attributes
    ----------
    name : string
    use_cache : bool
        If set to `True` then the generated information is cached for further computation. This requires that the
        used snapshots have an index > 0 which means they need to have been saved to the storage.
    use_storage : bool
        If set to `True` the cached information will also be stored in the associated netCDF file.
        This still needs testing.
    size : int
        The number of dimensions of the output order parameter. So far this is not used and will be necessary
        or useful when storage is available
    cache : SnapshotCache
        A cache object that holds all the values.
        
    Notes
    -----        
    Do we want to save this in the netCDF?
    And if yes, do we want one big table for all OrderParameters or several ones. One for each. Second might be nicer.
    '''

    def __init__(self, name):
        # Name needed to eventually store to netCDF. This is not yet done
        self.name = name

        # We will use a cache since we assume the snapshots objects, the OrderParameter Instance and the ID# of snapshots to be immutable
        self.use_cache = True
        self.use_storage = False
        
        # Run the OrderParameter on the initial snapshot to get the size
#        self.size = len(self._eval(0))
        self.size = 1
        
        if self.use_cache:
            self.cache = SnapshotCache(name = self.name, fnc = self._eval_idx)
        else:
            self.cache = None
            
    def _eval(self, trajectory, path = None):
        '''
        Actual evaluation of a list of snapshots.
        '''
        pass
    
    def _eval_idx(self, indices, path = None):
        '''
        Actual evaluation of indices of snapshots. Default version applies
        self._eval to all the indices.
        '''
        return self._eval(Trajectory(Configuration.get(indices)))

    def __call__(self, snapshot):
        '''
        Calculates the actual order parameter by making the OrderParameter object into a function
        
        Parameters
        ----------
        snapshot : Snapshot
            snapshot object used to compute the lambda value
            
        Returns
        -------
        
        float
            the actual value of the orderparameter from the given snapshot
        
        '''
        return self._assign(snapshot)        
    

    
    def _assign(self, snapshots):
        '''
        Assign a single snapshot or a trajectory.
        
        Parameters
        ----------
        snapshot : Snapshot
            A list of or a single snapshot that should be assigned
            
        Returns
        -------
        float
            the computed orderparameters
            
        Notes
        -----
        This calls self._eval with the relevant snapshots.
        '''
        single = False
        
        if type(snapshots) is Snapshot:
            traj = Trajectory([snapshots])
            single = True
        else:
            traj = snapshots

        traj_indices = traj.configurations()
        
        if self.use_cache:
            # pick all non-stored snapshots and compute these anyway without storage
            no_index = [ i for i,idx in enumerate(traj_indices) if idx == 0]
            
            d = self.cache[traj_indices]
            
            if len(no_index) > 0:
                # compute ones that cannot be cached
                d_no_index = self._eval(traj[no_index])      
                    
                # add unknowns
                for ind, dist in enumerate(d_no_index):
                    d[no_index[ind]] = dist
                                                
        else: 
            d = self._eval(traj_indices)

        if single:
            return d[0]
        else:
            return d    
    
    @staticmethod
    def _scale_fnc(mi, ma):
        '''
        Helper function that returns a function that scale values in a specified range to a range between 0 and 1.
        
        Parameters
        ----------
        mi : float
            Minimal value. Corresponds to zero.
        ma : float
            Maximal value. Corresponds to one.
            
        Returns
        -------
        function
            The scaling function of float -> float
        
        '''
        
        def scale(x):
            if x < mi:
                return 0.0
            elif x > ma:
                return 1.0
            else:
                return (x-mi) / (ma-mi)
            
        return scale
        
        
class OP_RMSD_To_Lambda(OrderParameter):
    '''
    An OrderParameter that transforms the RMSD to a specific center to a lambda value between zero and one.
    
    Parameters
    ----------
    center : snapshot
        a trajectory snapshot that is used as the point to compute the RMSD to
    lambda_min : float
        rmsd value that corresponds to lambda zero
    max_lambda : float
        rmsd value that corresponds to lambda one
    atom_indices : list of integers (optional)
        a list of integers that is used in the rmsd computation. Usually solvent should be excluded

    Attributes
    ----------
    center : snapshot
        a trajectory snapshot that is used as the point to compute the RMSD to
    lambda_min : float
        rmsd value that corresponds to lambda zero
    max_lambda : float
        rmsd value that corresponds to lambda one
    atom_indices : list of integers (optional)
        a list of integers that is used in the rmsd computation. Usually solvent should be excluded
    metric : msmbuilder.metrics.RMSD
        the RMSD metric object used to compute the RMSD
    _generator : mdtraj.Trajectory prepared by metric.prepare_trajectory
        trajectory object that contains only the center configuration to which the RMSD is computed to            
    '''
    
    def __init__(self, name, center, lambda_min, max_lambda, atom_indices = None):
        super(OP_RMSD_To_Lambda, self).__init__(name)
                
        self.atom_indices = atom_indices
        self.center = center
        self.min_lambda = lambda_min
        self.max_lambda = max_lambda
        
        self.size = 1
                
        # Generate RMSD metric using only the needed indices. To save memory we crop the read snapshots from the database and do not use a cropping RMSD on the full snapshots
        self.metric = RMSD(None)
        self._generator = self.metric.prepare_trajectory(Trajectory([center]).subset(self.atom_indices).md())  
        return 
    
    ################################################################################
    ##  Actual computation of closest point using RMSD
    ################################################################################    
    
    def _eval_idx(self, indices):
        return self._eval(Trajectory(Configuration.get(indices)))
    
    def _eval(self, trajectory):
        ptraj = self.metric.prepare_trajectory(trajectory.subset(self.atom_indices).md())
        results = self.metric.one_to_all(self._generator, ptraj, 0)
                
        return map(self._scale_fnc(self.min_lambda, self.max_lambda), results )

class OP_Multi_RMSD(OrderParameter):
    '''
    An OrderParameter that transforms the RMSD to a set of centers.
    
    Parameters
    ----------
    centers : trajectory
        a trajectory of snapshots that are used as the points to compute the RMSD to
    atom_indices : list of integers (optional)
        a list of integers that is used in the rmsd computation. Usually solvent should be excluded
    metric : msmbuilder.metrics.Metric
        the metric object used to compute the RMSD

    Attributes
    ----------
    centers : trajectory
        a trajectory of snapshots that are used as the points to compute the RMSD to
    atom_indices : list of integers (optional)
        a list of integers that is used in the rmsd computation. Usually solvent should be excluded
    metric : msmbuilder.metrics.RMSD
        the RMSD metric object used to compute the RMSD
    '''
    
    def __init__(self, name, centers, atom_indices = None, metric = None):
        super(OP_Multi_RMSD, self).__init__(name)
                
        self.atom_indices = atom_indices
        self.center = centers
        
        self.size = len(centers)
                
        # Generate RMSD metric using only the needed indices. To save memory we crop the read snapshots from the database and do not use a cropping RMSD on the full snapshots
        if metric is None:
            self.metric = RMSD(None)
        else:
            self.metric = metric
        self._generator = self.metric.prepare_trajectory(centers.subset(self.atom_indices).md())  
        return 
    
    def _eval_idx(self, indices):
        return self._eval(Trajectory(Configuration.get(indices)))
    
    def _eval(self, trajectory):
        ptraj = self.metric.prepare_trajectory(trajectory.subset(self.atom_indices).md())
        return [ self.metric.one_to_all(ptraj, self._generator, idx) for idx in range(0,len(ptraj)) ]
    
class OP_Function(OrderParameter):
    """ Wrapper to decorate any appropriate function as an OrderParameter.

    Examples
    -------
    >>> # To create an order parameter which calculates the dihedral formed
    >>> # by atoms [7,9,15,17] (psi in Ala dipeptide):
    >>> import mdtraj as md
    >>> psi_atoms = [7,9,15,17]
    >>> psi_orderparam = OP_Function("psi", md.compute_dihedrals,
    >>>                              trajdatafmt="mdtraj",
    >>>                              indices=[phi_atoms])
    >>> print psi_orderparam( traj.md() )
    """
    def __init__(self, name, fcn, trajdatafmt=None, **kwargs):
        """
        Parameters
        ----------
        name : str
        fcn : function
        trajdatafmt : str
            which format the trajectory data needs to be in for the `fcn`.
            Currently supports "mdtraj", otherwise defaults to our own 
        kwargs : 
            named arguments which should be given to `fcn` (for example, the
            atoms which define a specific distance/angle)

        Notes
        -----
            We may decide that it is better not to use the trajdatafmt
            trick, and to instead create separate wrapper classes for each
            supported trajformat.
        """
        super(OP_Function, self).__init__(name)
        self.fcn = fcn
        self.trajdatafmt = trajdatafmt
        self.kwargs = kwargs
        return


    def _eval(self, trajectory, *args):
        if self.trajdatafmt=='mdtraj':
            t = trajectory.md()
        else:
            t = trajectory
        return self.fcn(t, *args, **self.kwargs)
    


if __name__ == '__main__':
    def ident(indices):
        if type(indices) is list:
            return [float(i) for i in indices]
        else:
            return float(indices)
        
    s = SnapshotCache(name = 'TestList', fnc = ident)
    
    print s[10]
    print s[5]
    print s[5]
    print s.cache
    print s[1:10]
    print s.cache


