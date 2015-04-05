###############################################################
# | CLASS Order Parameter
###############################################################

import mdtraj as md
import openpathsampling as paths
import chaindict as cd
import collections
from openpathsampling.util.todict import ops_object


@ops_object
class CollectiveVariable(cd.Wrap):
    """
    Wrapper for a function that maps a snapshot to a number.

    Parameters
    ----------
    name : string
        A descriptive name of the collectivevariable. It is used in the string
        representation.
    dimensions : int
        The number of dimensions of the output order parameter. So far this
        is not used and will be necessary or useful when storage is
        available
    storages : list of ConfigurationStorages()
        contains the list of storages that will be used.

    Attributes
    ----------
    name
    dimensions
    storages

    """

    def __init__(self, name, dimensions=1):
        if (type(name) is not str and type(name) is not unicode) or len(name) == 0:
            print type(name), len(name)
            raise ValueError('name must be a non-empty string')

        self.name = name

        self.pre_dict = cd.Transform(self._pre_item)
        self.multi_dict = cd.ExpandMulti()
        self.store_dict = cd.MultiStore('collectivevariables', name,
                                            dimensions, self)
        self.cache_dict = cd.ChainDict()
        if hasattr(self, '_eval'):
            self.expand_dict = cd.UnwrapTuple()
            self.func_dict = cd.Function(None)

            self.func_dict._eval = self._eval

            super(CollectiveVariable, self).__init__(
                post=self.func_dict + self.expand_dict + self.cache_dict +
                     self.store_dict + self.multi_dict + self.pre_dict
            )

        else:
            super(CollectiveVariable, self).__init__(
                post=self.cache_dict + self.store_dict + self.multi_dict + self.pre_dict
            )

        self._stored = False

    def flush_cache(self, storage):
        """
        Copy the cache to the internal storage cache for saving

        Parameters
        ----------
        storage : Storage()
            the storage for which the cache should be copied
        """
        if storage in self.store_dict.cod_stores:
            stored = {
                key : value for key, value in self.cache_dict
                    if type(key) is tuple or storage in key.idx
            }
            self.store_dict.cod_stores[storage].post.update(stored)
            self.store_dict.cod_stores[storage].update(stored)

    def sync(self, storage):
        """
        Sync this collectivevariable with attached storages

        Parameters
        ----------
        store : CollectiveVariableStore or None
            the store to be used, otherwise all underlying storages are synced
        store_cache : bool
            if `False` (default) the store will only store new values. If
            `True` also the cached values will be stored. This is much more
            costly and is usually only run once, when the collectivevariable is
            saved the first time
        """
        self.store_dict.update_nod_stores()
        if storage in self.store_dict.cod_stores:
            self.store_dict.cod_stores[storage].sync()

    def _pre_item(self, items):
        item_type = self.store_dict._basetype(items)

        if item_type is paths.Snapshot:
            return items
        elif item_type is paths.Trajectory:
            return list(list.__iter__(items))
        elif isinstance(items, collections.Iterable):
            item_sub_type = self.store_dict._basetype(iter(items).next())
            if item_sub_type is paths.Snapshot:
                return items
            else:
                raise KeyError('the collectivevariable is only compatible with ' +
                               'snapshots, trajectories or other iteratble of snapshots!')
                return None
        else:
            return None


@ops_object
class CV_RMSD_To_Lambda(CollectiveVariable):
    """
    Transforms the RMSD from `center` to a value between zero and one.

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
    """

    def __init__(self, name, center, lambda_min, max_lambda, atom_indices=None):
        super(CV_RMSD_To_Lambda, self).__init__(name, dimensions=1)

        self.atom_indices = atom_indices
        self.center = center
        self.min_lambda = lambda_min
        self.max_lambda = max_lambda

        self._generator = paths.Trajectory([center]).subset(
            self.atom_indices).md()
        return

    ################################################################################
    ##  Actual computation of closest point using RMSD
    ################################################################################

    @staticmethod
    def _scale_fnc(mi, ma):
        def scale(x):
            if x < mi:
                return 0.0
            elif x > ma:
                return 1.0
            else:
                return (x - mi) / (ma - mi)

        return scale

    def _eval(self, items):
        trajectory = paths.Trajectory(items)
        ptraj = trajectory.subset(self.atom_indices).md()

        results = md.rmsd(ptraj, self._generator)

        return map(self._scale_fnc(self.min_lambda, self.max_lambda), results)


@ops_object
class CV_Featurizer(CollectiveVariable):
    """
    An CollectiveVariable that uses an MSMBuilder3 featurizer as the logic

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
    """

    def __init__(self, name, featurizer, atom_indices=None):
        super(CV_Featurizer, self).__init__(name,
                                            dimensions=featurizer.n_features)

        self.atom_indices = atom_indices
        self.featurizer = featurizer

        return

    def _eval(self, items):
        trajectory = paths.Trajectory(items)

        # create an MDtraj trajectory out of it
        ptraj = trajectory.subset(self.atom_indices).md()

        # run the featurizer
        result = self.featurizer.partial_transform(ptraj)

        return result


@ops_object
class CV_MD_Function(CollectiveVariable):
    """Make `CollectiveVariable` from `fcn` that takes mdtraj.trajectory as input.

    Examples
    -------
    >>> # To create an order parameter which calculates the dihedral formed
    >>> # by atoms [7,9,15,17] (psi in Ala dipeptide):
    >>> import mdtraj as md
    >>> psi_atoms = [7,9,15,17]
    >>> psi_orderparam = CV_Function("psi", md.compute_dihedrals,
    >>>                              indices=[phi_atoms])
    >>> print psi_orderparam( traj.md() )
    """

    def __init__(self, name, fcn, **kwargs):
        """
        Parameters
        ----------
        name : str
        fcn : function
        kwargs :
            named arguments which should be given to `fcn` (for example, the
            atoms which define a specific distance/angle)

        """
        super(CV_MD_Function, self).__init__(name)
        self.fcn = fcn
        self.kwargs = kwargs
        self.topology = None
        return

    def _eval(self, items, *args):
        trajectory = paths.Trajectory(items)

        if self.topology is None:
            # first time ever compute the used topology for this collectivevariable to construct the mdtraj objects
            self.topology = trajectory.topology.md

        t = trajectory.md(self.topology)
        return self.fcn(t, *args, **self.kwargs)


@ops_object
class CV_Volume(CollectiveVariable):
    """ Make `Volume` into `CollectiveVariable`: maps to 0.0 or 1.0 """

    def __init__(self, name, volume):
        """
        Parameters
        ----------

        """

        super(CV_Volume, self).__init__(name)
        self.volume = volume

    def _eval(self, items):
        result = [float(self.volume(item)) for item in items]
        return result


@ops_object
class CV_Function(CollectiveVariable):
    """Make any function `fcn` into an `CollectiveVariable`.

    Examples
    -------
    >>> # To create an order parameter which calculates the dihedral formed
    >>> # by atoms [7,9,15,17] (psi in Ala dipeptide):
    >>> import mdtraj as md
    >>> psi_atoms = [6,8,14,16]
    >>> psi_orderparam = CV_Function("psi", md.compute_dihedrals,
    >>>                              trajdatafmt="mdtraj",
    >>>                              indices=[psi_atoms])
    >>> print psi_orderparam( traj.md() )
    """

    def __init__(self, name, fcn, **kwargs):
        """
        Parameters
        ----------
        name : str
        fcn : function
        kwargs :
            named arguments which should be given to `fcn` (for example, the
            atoms which define a specific distance/angle)

        Notes
        -----
            We may decide that it is better not to use the trajdatafmt
            trick, and to instead create separate wrapper classes for each
            supported trajformat.
        """
        super(CV_Function, self).__init__(name)
        self._fcn = fcn
        self.kwargs = kwargs
        return


    def _eval(self, items, *args):
        trajectory = paths.Trajectory(items)

        return [self._fcn(snap, *args, **self.kwargs) for snap in trajectory]
