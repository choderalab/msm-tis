import mdtraj as md
import numpy as np
import pandas as pd
from simtk import unit as units
import simtk.openmm

from openpathsampling.dynamics.topology import Topology
from openpathsampling.todict import ops_object


@ops_object
class MDTrajTopology(Topology):
    def __init__(self, mdtraj_topology, subsets = None):
        self.md = mdtraj_topology
        self.n_atoms = int(mdtraj_topology.n_atoms)
        self.n_spatial = 3
        if subsets is None:
            self.subsets = {}
        else:
            self.subsets = subsets

    def subset(self, list_of_atoms):
        return MDTrajTopology(self.md.subset(list_of_atoms), self.subsets)

    def to_dict(self):
        out = dict()
        used_elements = set()

        atom_data = []
        for atom in self.md.atoms:
            if atom.element is None:
                element_symbol = ""
            else:
                element_symbol = atom.element.symbol

            atom_data.append((int(atom.serial), atom.name, element_symbol,
                         int(atom.residue.resSeq), atom.residue.name,
                         atom.residue.chain.index))

            used_elements.add(atom.element)

        out['atom_columns'] = ["serial", "name", "element", "resSeq", "resName", "chainID"]
        out['atoms'] = atom_data
        out['bonds'] = [(a.index, b.index) for (a, b) in self.md.bonds]
        out['elements'] = {key: tuple(el) for key, el in md.element.Element._elements_by_symbol.iteritems() if el in used_elements}

        return {'md' : out, 'subsets' : self.subsets}

    @classmethod
    def from_dict(cls, dct):
        top_dict = dct['md']
        elements = top_dict['elements']

        for key, el in elements.iteritems():
            try:
                md.element.Element(
                            number=int(el[0]), name=el[1], symbol=el[2], mass=float(el[3])
                         )
                simtk.openmm.app.Element(
                            number=int(el[0]), name=el[1], symbol=el[2], mass=float(el[3])*units.amu
                         )
            except(AssertionError):
                pass

        atoms = pd.DataFrame(top_dict['atoms'], columns=top_dict['atom_columns'])
        bonds = np.array(top_dict['bonds'])

        md_topology = md.Topology.from_dataframe(atoms, bonds)

        return cls(md_topology, dct['subsets'])
