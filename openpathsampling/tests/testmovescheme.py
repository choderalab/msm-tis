from nose.tools import (assert_equal, assert_not_equal, assert_items_equal,
                        assert_almost_equal, assert_in, raises, assert_is,
                        assert_is_not)
from nose.plugins.skip import Skip, SkipTest
from test_helpers import true_func, assert_equal_array_array, make_1d_traj

import copy

import openpathsampling as paths
from openpathsampling import VolumeFactory as vf
from openpathsampling.analysis.move_scheme import *
from openpathsampling.analysis.move_strategy import (
    levels,
    MoveStrategy, OneWayShootingStrategy, NearestNeighborRepExStrategy,
    DefaultStrategy, AllSetRepExStrategy
)

import logging
logging.getLogger('openpathsampling.initialization').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.ensemble').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.storage').setLevel(logging.CRITICAL)

class testMoveScheme(object):
    def setup(self):
        cvA = paths.CV_Function(name="xA", fcn=lambda s : s.xyz[0][0])
        cvB = paths.CV_Function(name="xB", fcn=lambda s : -s.xyz[0][0])
        self.stateA = paths.CVRangeVolume(cvA, float("-inf"), -0.5)
        self.stateB = paths.CVRangeVolume(cvB, float("-inf"), -0.5)
        interfacesA = vf.CVRangeVolumeSet(cvA, float("-inf"), 
                                          [-0.5, -0.3, -0.1, 0.0])
        interfacesB = vf.CVRangeVolumeSet(cvB, float("-inf"), 
                                          [-0.5, -0.3, -0.1, 0.0])
        network = paths.MSTISNetwork([
            (self.stateA, interfacesA, "A", cvA),
            (self.stateB, interfacesB, "B", cvB)
        ])
        self.scheme = MoveScheme(network)

    def test_append_individuals_default_levels(self):
        shootstrat = OneWayShootingStrategy()
        repexstrat = NearestNeighborRepExStrategy()
        defaultstrat = DefaultStrategy()
        assert_equal(len(self.scheme.strategies.keys()), 0)
        self.scheme.append(shootstrat)
        self.scheme.append(repexstrat)
        self.scheme.append(defaultstrat)

        strats = self.scheme.strategies
        assert_equal(len(strats.keys()), 3)
        pairs = [(levels.MOVER, shootstrat), (levels.SIGNATURE, repexstrat), 
                 (levels.GLOBAL, defaultstrat)]
        for (k, v) in pairs:
            assert_in(v, strats[k])

    def test_append_groups_default_levels(self):
        shootstrat = OneWayShootingStrategy()
        repexstrat = NearestNeighborRepExStrategy()
        defaultstrat = DefaultStrategy()
        assert_equal(len(self.scheme.strategies.keys()), 0)
        self.scheme.append([shootstrat, repexstrat, defaultstrat])

        strats = self.scheme.strategies
        assert_equal(len(strats.keys()), 3)
        pairs = [(levels.MOVER, shootstrat), (levels.SIGNATURE, repexstrat), 
                 (levels.GLOBAL, defaultstrat)]
        for (k, v) in pairs:
            assert_in(v, strats[k])


    def test_append_individuals_custom_levels(self):
        shootstrat = OneWayShootingStrategy()
        repexstrat = NearestNeighborRepExStrategy()
        defaultstrat = DefaultStrategy()
        assert_equal(len(self.scheme.strategies.keys()), 0)
        self.scheme.append(shootstrat, 60)
        self.scheme.append(repexstrat, 60)
        self.scheme.append(defaultstrat, 60)

        strats = self.scheme.strategies
        assert_equal(len(strats.keys()), 1)
        assert_items_equal(strats[60], [shootstrat, repexstrat, defaultstrat])

    def test_append_groups_same_custom_level(self):
        shootstrat = OneWayShootingStrategy()
        repexstrat = NearestNeighborRepExStrategy()
        defaultstrat = DefaultStrategy()
        assert_equal(len(self.scheme.strategies.keys()), 0)
        self.scheme.append([shootstrat, repexstrat, defaultstrat], 60)

        strats = self.scheme.strategies
        assert_equal(len(strats.keys()), 1)
        assert_items_equal(strats[60], [shootstrat, repexstrat, defaultstrat])

    def test_append_group_different_custom_levels(self):
        shootstrat = OneWayShootingStrategy()
        repexstrat = NearestNeighborRepExStrategy()
        defaultstrat = DefaultStrategy()
        assert_equal(len(self.scheme.strategies.keys()), 0)
        self.scheme.append([shootstrat, repexstrat, defaultstrat], 
                           [45, 55, 65])

        strats = self.scheme.strategies
        assert_equal(len(strats.keys()), 3)
        for (k, v) in [(45, shootstrat), (55, repexstrat), (65, defaultstrat)]:
            assert_in(v, strats[k])

    def test_apply_strategy(self):
        if self.scheme.movers == {}:
            print "Full support of MoveStrategy implemented?"
            print "Time to remove legacy from tests."
        else:
            self.scheme.movers = {} 

        shoot_strat_1 = OneWayShootingStrategy(
            ensembles=self.scheme.network.sampling_transitions[0].ensembles,
            replace=False
        )
        shoot_strat_2 = OneWayShootingStrategy(
            ensembles=(
                [self.scheme.network.sampling_transitions[0].ensembles[-1]] + 
                self.scheme.network.sampling_transitions[1].ensembles
            ),
            replace=False
        )
        shoot_strat_3 = OneWayShootingStrategy(replace=True)

        self.scheme.apply_strategy(shoot_strat_1)
        assert_items_equal(self.scheme.movers.keys(), ['shooting'])
        assert_equal(len(self.scheme.movers['shooting']), 3)

        self.scheme.apply_strategy(shoot_strat_2)
        assert_items_equal(self.scheme.movers.keys(), ['shooting'])
        assert_equal(len(self.scheme.movers['shooting']), 7)
        old_movers = copy.copy(self.scheme.movers['shooting'])

        self.scheme.apply_strategy(shoot_strat_3)
        assert_items_equal(self.scheme.movers.keys(), ['shooting'])
        assert_equal(len(self.scheme.movers['shooting']), 7)
        new_movers = self.scheme.movers['shooting']
        for (o, n) in zip(old_movers, new_movers):
            assert_equal(o is n, False)

        shoot_strat_3.replace_signatures = True
        self.scheme.apply_strategy(shoot_strat_3)
        assert_equal(len(self.scheme.movers['shooting']), 6)

        self.scheme.movers = {}
        shoot_strat_1.set_replace(True)
        self.scheme.apply_strategy(shoot_strat_1)
        assert_equal(len(self.scheme.movers['shooting']), 3)
        old_movers = copy.copy(self.scheme.movers['shooting'])

        shoot_strat_3.replace_signatures = False
        self.scheme.apply_strategy(shoot_strat_3)
        assert_equal(len(self.scheme.movers['shooting']), 6)
        new_movers = self.scheme.movers['shooting']
        for (o, n) in zip(old_movers, new_movers):
            assert_equal(o is n, False)

    def test_move_decision_tree(self):
        self.scheme.movers = {} # LEGACY
        shoot = OneWayShootingStrategy()
        repex = NearestNeighborRepExStrategy()
        default = DefaultStrategy()
        self.scheme.append([default, shoot, repex])
    
        assert_equal(self.scheme.root_mover, None)
        root = self.scheme.move_decision_tree()
        assert_not_equal(self.scheme.root_mover, None)

        assert_equal(len(root.movers), 2)
        names = ['ShootingChooser', 'RepexChooser']
        name_dict = {root.movers[i].name : i for i in range(len(root.movers))}
        for name in names:
            assert_in(name, name_dict.keys())

        assert_equal(len(root.movers[name_dict['ShootingChooser']].movers), 6)
        assert_equal(len(root.movers[name_dict['RepexChooser']].movers), 4)

        new_root = self.scheme.move_decision_tree()
        assert_is(new_root, root)

        new_root = self.scheme.move_decision_tree(rebuild=True)
        assert_is_not(new_root, root)

    def test_repex_style_switching(self):
        self.scheme.movers = {} # LEGACY
        nn_repex = NearestNeighborRepExStrategy()
        all_repex = AllSetRepExStrategy()
        default = DefaultStrategy()
        
        self.scheme.append([default, nn_repex])
        root = self.scheme.move_decision_tree(rebuild=True)
        assert_equal(len(self.scheme.movers['repex']), 4)

        self.scheme.append(all_repex)
        root = self.scheme.move_decision_tree(rebuild=True)
        assert_equal(len(self.scheme.movers['repex']), 6)

        self.scheme.append(nn_repex)
        root = self.scheme.move_decision_tree(rebuild=True)
        assert_equal(len(self.scheme.movers['repex']), 4)

    def test_build_balance_partners(self):
        self.scheme.movers = {} #LEGACY
        ensA = self.scheme.network.sampling_transitions[0].ensembles[0]
        ensB = self.scheme.network.sampling_transitions[0].ensembles[1]
        hopAB = paths.EnsembleHopMover(ensemble=ensA, target_ensemble=ensB)
        hopBA = paths.EnsembleHopMover(ensemble=ensB, target_ensemble=ensA)
        self.scheme.movers['hop'] = [hopAB, hopBA]
        self.scheme.append(strategies.DefaultStrategy())
        root = self.scheme.move_decision_tree()
        self.scheme.build_balance_partners()
        assert_equal(self.scheme.balance_partners[hopAB], [hopBA])
        assert_equal(self.scheme.balance_partners[hopBA], [hopAB])

    @raises(RuntimeWarning)
    def test_build_balance_partners_premature(self):
        self.scheme.movers = {}
        self.scheme.build_balance_partners()

    @raises(RuntimeWarning)
    def test_build_balance_partners_no_partner(self):
        self.scheme.movers = {} #LEGACY
        ensA = self.scheme.network.sampling_transitions[0].ensembles[0]
        ensB = self.scheme.network.sampling_transitions[0].ensembles[1]
        hopAB = paths.EnsembleHopMover(ensemble=ensA, target_ensemble=ensB)
        hopBA = paths.EnsembleHopMover(ensemble=ensB, target_ensemble=ensA)
        self.scheme.movers['hop'] = [hopAB]
        self.scheme.append(strategies.DefaultStrategy())
        root = self.scheme.move_decision_tree()
        self.scheme.build_balance_partners()

    @raises(RuntimeWarning)
    def test_build_balance_partners_two_partners(self):
        self.scheme.movers = {} #LEGACY
        ensA = self.scheme.network.sampling_transitions[0].ensembles[0]
        ensB = self.scheme.network.sampling_transitions[0].ensembles[1]
        hopAB = paths.EnsembleHopMover(ensemble=ensA, target_ensemble=ensB)
        hopAB2 = paths.EnsembleHopMover(ensemble=ensA, target_ensemble=ensB)
        hopBA = paths.EnsembleHopMover(ensemble=ensB, target_ensemble=ensA)
        self.scheme.movers['hop'] = [hopAB, hopBA, hopAB2]
        self.scheme.append(strategies.DefaultStrategy())
        root = self.scheme.move_decision_tree()
        self.scheme.build_balance_partners()

    def test_sanity_check_sane(self):
        self.scheme.movers = {} #LEGACY
        self.scheme.append([NearestNeighborRepExStrategy(),
                            OneWayShootingStrategy(), DefaultStrategy()])
        root = self.scheme.move_decision_tree()
        self.scheme.sanity_check()

    @raises(AssertionError)
    def test_sanity_check_unused_sampling(self):
        self.scheme.movers = {} #LEGACY
        ensemble_subset = self.scheme.network.sampling_transitions[0].ensembles
        self.scheme.append([
            OneWayShootingStrategy(ensembles=ensemble_subset),
            DefaultStrategy()
        ])
        root = self.scheme.move_decision_tree()
        self.scheme.sanity_check()

    @raises(AssertionError)
    def test_sanity_check_choice_prob_fails(self):
        self.scheme.movers = {} #LEGACY
        self.scheme.append([NearestNeighborRepExStrategy(),
                            OneWayShootingStrategy(), DefaultStrategy()])
        root = self.scheme.move_decision_tree()
        key0 = self.scheme.choice_probability.keys()[0]
        self.scheme.choice_probability[key0] = 0.0
        self.scheme.sanity_check()

    @raises(AssertionError)
    def test_sanity_check_duplicated_movers(self):
        self.scheme.movers = {} #LEGACY
        ensemble_subset = self.scheme.network.sampling_transitions[0].ensembles
        self.scheme.append([
            OneWayShootingStrategy(),
            DefaultStrategy()
        ])
        root = self.scheme.move_decision_tree()
        self.scheme.movers['foo'] = [self.scheme.movers['shooting'][0]]
        self.scheme.sanity_check()

    @raises(TypeError)
    def test_select_movers_no_choice_probability(self):
        self.scheme.movers = {} # LEGACY
        self.scheme.append([OneWayShootingStrategy(), DefaultStrategy()])
        movers = self.scheme._select_movers('shooting')

    def test_select_movers(self):
        self.scheme.movers = {} # LEGACY
        self.scheme.append([
            OneWayShootingStrategy(), 
            NearestNeighborRepExStrategy(),
            DefaultStrategy()
        ])
        root = self.scheme.move_decision_tree()
        some_shooters = self.scheme.movers['shooting'][0:2]

        movers = self.scheme._select_movers('shooting')
        assert_equal(movers, self.scheme.movers['shooting'])

        movers = self.scheme._select_movers(some_shooters)
        assert_equal(movers, some_shooters)

        movers = self.scheme._select_movers(some_shooters[0])
        assert_equal(movers, [some_shooters[0]])

    def test_n_trials_for_steps(self):
        self.scheme.movers = {} # LEGACY
        self.scheme.append([
            OneWayShootingStrategy(), 
            NearestNeighborRepExStrategy(),
            DefaultStrategy()
        ])
        root = self.scheme.move_decision_tree()
        some_shooters = self.scheme.movers['shooting'][0:3]

        assert_almost_equal(
            self.scheme.n_trials_for_steps('shooting', 100),
            2.0/3.0*100
        )

        assert_almost_equal(
            self.scheme.n_trials_for_steps(some_shooters, 100),
            1.0/3.0*100
        )

        assert_almost_equal(
            self.scheme.n_trials_for_steps(some_shooters[0], 100),
            1.0/9.0*100
        )


    def test_n_steps_for_trials(self):
        self.scheme.movers = {} # LEGACY
        self.scheme.append([
            OneWayShootingStrategy(), 
            NearestNeighborRepExStrategy(),
            DefaultStrategy()
        ])
        root = self.scheme.move_decision_tree()
        some_shooters = self.scheme.movers['shooting'][0:3]

        assert_almost_equal(
            self.scheme.n_steps_for_trials('shooting', 100), 150.0
        )

        assert_almost_equal(
            self.scheme.n_steps_for_trials(some_shooters, 100), 300.0
        )

        assert_almost_equal(
            self.scheme.n_steps_for_trials(some_shooters[0], 100), 900.0
        )



class testDefaultScheme(object):
    def setup(self):
        cvA = paths.CV_Function(name="xA", fcn=lambda s : s.xyz[0][0])
        cvB = paths.CV_Function(name="xB", fcn=lambda s : -s.xyz[0][0])
        self.stateA = paths.CVRangeVolume(cvA, float("-inf"), -0.5)
        self.stateB = paths.CVRangeVolume(cvB, float("-inf"), -0.5)
        interfacesA = vf.CVRangeVolumeSet(cvA, float("-inf"), 
                                          [-0.5, -0.3, -0.1, 0.0])
        interfacesB = vf.CVRangeVolumeSet(cvB, float("-inf"), 
                                          [-0.5, -0.3, -0.1, 0.0])
        self.network = paths.MSTISNetwork([
            (self.stateA, interfacesA, "A", cvA),
            (self.stateB, interfacesB, "B", cvB)
        ])
    
    def test_default_scheme(self):
        scheme = DefaultScheme(self.network)
        scheme.movers = {} # LEGACY
        root = scheme.move_decision_tree()
        chooser_type_dict = {
            'ShootingChooser' : paths.OneWayShootingMover,
            'PathreversalChooser' : paths.PathReversalMover,
            'RepexChooser' : paths.ReplicaExchangeMover,
            'MinusChooser' : paths.MinusMover,
            'Ms_outer_shootingChooser' : paths.OneWayShootingMover
        }
        names = chooser_type_dict.keys()

        assert_equal(len(root.movers), len(names))

        name_dict = {root.movers[i].name : i for i in range(len(root.movers))}
        for name in names:
            assert_in(name, name_dict.keys())

        n_normal_repex = 4
        n_msouter_repex = 2
        n_repex = n_normal_repex + n_msouter_repex

        assert_equal(
            len(root.movers[name_dict['ShootingChooser']].movers), 6
        )
        assert_equal(
            len(root.movers[name_dict['PathreversalChooser']].movers), 7
        )
        assert_equal(
            len(root.movers[name_dict['RepexChooser']].movers), n_repex
        )
        assert_equal(
            len(root.movers[name_dict['MinusChooser']].movers), 2
        )
        assert_equal(
            len(root.movers[name_dict['Ms_outer_shootingChooser']].movers), 1
        )

        for choosername in names:
            for mover in root.movers[name_dict[choosername]].movers:
                assert_equal(type(mover), chooser_type_dict[choosername])


    def test_default_sanity(self):
        scheme = DefaultScheme(self.network)
        scheme.movers = {} # LEGACY
        root = scheme.move_decision_tree()
        scheme.sanity_check()

    def test_default_hidden_ensembles(self):
        scheme = DefaultScheme(self.network)
        scheme.movers = {} # LEGACY
        root = scheme.move_decision_tree()
        hidden = scheme.find_hidden_ensembles()
        assert_equal(len(hidden), 2)

    def test_default_unused_ensembles(self):
        scheme = DefaultScheme(self.network)
        scheme.movers = {} # LEGACY
        root = scheme.move_decision_tree()
        unused = scheme.find_unused_ensembles()
        assert_equal(len(unused), 0) # will change when minus/msouter 

    def test_default_balance_partners(self):
        scheme = DefaultScheme(self.network)
        scheme.movers = {} # LEGACY
        root = scheme.move_decision_tree()
        scheme.build_balance_partners()
        # by default, every mover is its own balance partner
        for group in scheme.movers.values():
            for mover in group:
                assert_equal(scheme.balance_partners[mover], [mover])


    def test_default_choice_probability(self):
        scheme = DefaultScheme(self.network)
        scheme.movers = {} # LEGACY
        root = scheme.move_decision_tree()
        default_group_weights = {
            'shooting' : 1.0,
            'repex' : 0.5,
            'pathreversal' : 0.5,
            'minus' : 0.2,
            'ms_outer_shooting' : 1.0
        }

        assert_almost_equal(sum(scheme.choice_probability.values()), 1.0)

        tot_norm = sum([default_group_weights[group] 
                        for group in scheme.movers])

        for groupname in scheme.movers.keys():
            group = scheme.movers[groupname]
            n_movers = len(group)
            weight = default_group_weights[groupname] / tot_norm / n_movers
            for mover in group:
                assert_almost_equal(scheme.choice_probability[mover], weight)

        prob_shoot0 = scheme.choice_probability[scheme.movers['shooting'][0]]
        n_shooting = len(scheme.movers['shooting'])
        for group in default_group_weights:
            scale = default_group_weights[group]
            n_group = len(scheme.movers[group])
            assert_almost_equal(
                prob_shoot0 * n_shooting / n_group,
                scheme.choice_probability[scheme.movers[group][0]] / scale
            )


