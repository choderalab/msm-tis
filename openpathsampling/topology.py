from openpathsampling.util.todict import restores_as_full_object

__author__ = 'jan-hendrikprinz'

@restores_as_full_object
class Topology(object):
    '''
    Topology is the object that contains all information about the structure
    of the system to be simulated.

    Attributes
    ----------
    n_atoms : int
        number of atoms
    spatial : int
        number of spatial dimensions, default is 3
    '''

    def __init__(self, n_atoms, n_spatial = 3):
        self.n_atoms = n_atoms
        self.n_spatial = n_spatial

    def subset(self, list_of_atoms):
        return Topology(
            n_atoms=len(list_of_atoms),
            n_spatial=self.n_spatial
        )