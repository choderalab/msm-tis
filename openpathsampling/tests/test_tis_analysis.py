from nose.tools import (assert_equal, assert_not_equal, assert_items_equal,
                        assert_almost_equal, raises)
from nose.plugins.skip import Skip, SkipTest
from test_helpers import (
    true_func, assert_equal_array_array, make_1d_traj, data_filename,
    MoverWithSignature, RandomMDEngine
)

from openpathsampling.analysis.tis_analysis import *

import logging
logging.getLogger('openpathsampling.initialization').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.ensemble').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.storage').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.netcdfplus').setLevel(logging.CRITICAL)

def make_tis_traj_fixed_steps(n_steps, step_size=0.1, reverse=False):
    if reverse:
        sign = -1
        delta = 1.0
    else:
        sign = 1
        delta = 0.0
    rising = [delta + sign * (-0.5 + i) * step_size
              for i in range(n_steps + 2)]
    falling = list(reversed(rising))[1:]
    return make_1d_traj(rising + falling)


class TISAnalysisTester(object):
    # abstract class to give the same setup to all the test functions

    def _make_fake_steps(self, sample_sets, mover):
        steps = []
        for (mccycle, sample_set) in enumerate(sample_sets):
            change = paths.AcceptedSampleMoveChange(
                samples=sample_set.samples,
                mover=mover,
                details=None,
                input_samples=None
            )
            step = paths.MCStep(mccycle=mccycle,
                                active=sample_set,
                                change=change)
            steps.append(step)
        return steps

    def _make_fake_sampling_sets(self, network):
        ensembles_AB = self.sampling_ensembles_for_transition(
            network, self.state_A, self.state_B
        )
        ensembles_BA = self.sampling_ensembles_for_transition(
            network, self.state_B, self.state_A
        )

        all_ensembles = ensembles_AB + ensembles_BA
        replicas = range(len(all_ensembles))

        # This encodes how the SampleSets are at each time step. This is the
        # trajectory number (from trajs_AB/trajs_BA) for each ensemble
        # (index order of sampling_AB.ensembles + sampling_BA.ensembles)
        descriptions = [
            [2, 3, 3, 2, 3, 3],
            [1, 2, 3, 1, 2, 3],
            [0, 1, 2, 0, 1, 2],
            [0, 1, 2, 0, 1, 2]
        ]

        # here's the fancy fake data
        sample_sets = []
        for descr in descriptions:
            set_trajectories = ([self.trajs_AB[d] for d in descr[:3]]
                                + [self.trajs_BA[d] for d in descr[3:]])
            zipped = zip(set_trajectories, all_ensembles, replicas)
            sample_set = paths.SampleSet([
                paths.Sample(trajectory=traj,
                             ensemble=ens,
                             replica=rep)
                for (traj, ens, rep) in zip(set_trajectories, all_ensembles,
                                            range(len(all_ensembles)))
            ])
            sample_sets.append(sample_set)
        return sample_sets

    def sampling_ensembles_for_transition(self, network, state_A, state_B):
        analysis_AB = network.transitions[(state_A, state_B)]
        sampling_AB = network.analysis_to_sampling[analysis_AB][0]
        return sampling_AB.ensembles

    def setup(self):
        # set up the trajectories, ensembles, etc. for this test
        cv_A = paths.FunctionCV('Id', lambda s: s.xyz[0][0])
        cv_B = paths.FunctionCV('1-Id', lambda s: 1.0-s.xyz[0][0])
        self.cv_x = cv_A
        self.state_A = paths.CVDefinedVolume(cv_A, float("-inf"), 0.0)
        self.state_B = paths.CVDefinedVolume(cv_B, float("-inf"), 0.0)
        interfaces_AB = paths.VolumeInterfaceSet(cv_A, float("-inf"),
                                                 [0.0, 0.1, 0.2])
        interfaces_BA = paths.VolumeInterfaceSet(cv_B, float("-inf"),
                                                 [0.0, 0.1, 0.2])

        # trajectory that crosses each interface, one state-to-state
        self.trajs_AB = [make_tis_traj_fixed_steps(i) for i in [0, 1, 2]]
        self.trajs_AB += [make_1d_traj([(-0.5 + i) * 0.1 
                                        for i in range(12)])]

        self.trajs_BA = [make_tis_traj_fixed_steps(i, reverse=True)
                         for i in [0, 1, 2]]
        self.trajs_BA += [make_1d_traj([1.0 - (-0.5 + i) * 0.1
                                        for i in range(12)])]

        # set up mistis
        self.mistis = paths.MISTISNetwork([
            (self.state_A, interfaces_AB, self.state_B),
            (self.state_B, interfaces_BA, self.state_A)
        ])
        mover_stub_mistis = MoverWithSignature(self.mistis.all_ensembles,
                                               self.mistis.all_ensembles)

        mistis_ssets = self._make_fake_sampling_sets(self.mistis)
        self.mistis_steps = self._make_fake_steps(mistis_ssets,
                                                  mover_stub_mistis)

        self.mistis_weighted_trajectories = steps_to_weighted_trajectories(
            self.mistis_steps,
            self.mistis.sampling_ensembles
        )

        # TODO: set up mstis
        self.mstis = paths.MSTISNetwork([
            (self.state_A, interfaces_AB),
            (self.state_B, interfaces_BA)
        ])
        mover_stub_mstis = MoverWithSignature(self.mstis.all_ensembles,
                                              self.mstis.all_ensembles)
        mstis_ssets = self._make_fake_sampling_sets(self.mstis)
        self.mstis_steps = self._make_fake_steps(mstis_ssets,
                                                 mover_stub_mstis)

        self.mstis_weighted_trajectories = steps_to_weighted_trajectories(
            self.mstis_steps,
            self.mstis.sampling_ensembles
        )


class TestWeightedTrajectories(TISAnalysisTester):
    def _check_network_results(self, network, weighted_trajs):
        # works for both MISTIS and MSTIS, since they use equivalent data
        ensembles_AB = self.sampling_ensembles_for_transition(
            network, self.state_A, self.state_B
        )
        ensembles_BA = self.sampling_ensembles_for_transition(
            network, self.state_B, self.state_A
        )

        # (ensemble_number, trajectory_number): count
        results = {(0, 0): 2, (0, 1): 1, (0, 2): 1, (0, 3): 0,
                   (1, 0): 0, (1, 1): 2, (1, 2): 1, (1, 3): 1,
                   (2, 0): 0, (2, 1): 0, (2, 2): 2, (2, 3): 2}

        for ((ens, traj), result) in results.iteritems():
            assert_equal(
                weighted_trajs[ensembles_AB[ens]][self.trajs_AB[traj]],
                result
            )
            assert_equal(
                weighted_trajs[ensembles_BA[ens]][self.trajs_BA[traj]],
                result
            )

    def test_steps_to_weighted_trajectories(self):
        assert_equal(len(self.mistis_weighted_trajectories),
                     len(self.mistis.sampling_ensembles))
        self._check_network_results(self.mistis,
                                    self.mistis_weighted_trajectories)

        assert_equal(len(self.mstis_weighted_trajectories),
                     len(self.mstis.sampling_ensembles))
        self._check_network_results(self.mstis,
                                    self.mstis_weighted_trajectories)


class TestDictFlux(TISAnalysisTester):
    def setup(self):
        super(TestDictFlux, self).setup()
        self.innermost_interface_A = \
                self.sampling_ensembles_for_transition(self.mistis,
                                                       self.state_A,
                                                       self.state_B)[0]
        self.innermost_interface_B = \
                self.sampling_ensembles_for_transition(self.mistis,
                                                       self.state_B,
                                                       self.state_A)[0]

        self.flux_dict = {(self.state_A, self.innermost_interface_A): 1.0,
                          (self.state_B, self.innermost_interface_B): 1.0}
        self.flux_method = DictFlux(self.flux_dict)

    def test_calculate(self):
        assert_equal(self.flux_method.calculate(self.mistis_steps),
                     self.flux_dict)

    def test_from_weighted_trajectories(self):
        assert_equal(
            self.flux_method.from_weighted_trajectories(self.mistis_steps),
            self.flux_dict
        )

    def test_intermediates(self):
        assert_equal(self.flux_method.intermediates(self.mistis_steps), [])

    def test_calculate_from_intermediates(self):
        intermediates = self.flux_method.intermediates(self.mistis_steps)
        assert_equal(
            self.flux_method.calculate_from_intermediates(*intermediates),
            self.flux_dict
        )

    def test_combine_results(self):
        my_result = self.flux_method.calculate(self.mistis_steps)
        same_result = {(self.state_A, self.innermost_interface_A): 1.0,
                       (self.state_B, self.innermost_interface_B): 1.0}
        assert_equal(
            self.flux_method.combine_results(my_result, same_result),
            my_result
        )

    @raises(RuntimeError)
    def test_bad_combine_results(self):
        my_result = self.flux_method.calculate(self.mistis_steps)
        bad_result = {(self.state_A, self.innermost_interface_A): 2.0,
                      (self.state_B, self.innermost_interface_B): 2.0}
        self.flux_method.combine_results(my_result, bad_result)


class TestMinusMoveFlux(TISAnalysisTester):
    def setup(self):
        super(TestMinusMoveFlux, self).setup()

        a = 0.1  # just a number to simplify the trajectory-making
        minus_move_descriptions = [
            [-a, a, a, -a, -a, -a, -a, -a, a, a, a, a, a, -a],
            [-a, a, a, a, -a, -a, -a, a, a, a, -a]
        ]

        engine = RandomMDEngine()  # to get snapshot_timestep

        self.mistis_scheme = paths.DefaultScheme(self.mistis, engine)
        self.mistis_scheme.build_move_decision_tree()
        self.mistis_minus_steps = self._make_fake_minus_steps(
            scheme=self.mistis_scheme,
            descriptions=minus_move_descriptions
        )
        self.mistis_minus_flux = MinusMoveFlux(self.mistis_scheme)

        self.mstis_scheme = paths.DefaultScheme(self.mstis, engine)
        self.mstis_scheme.build_move_decision_tree()
        self.mstis_minus_steps = self._make_fake_minus_steps(
            scheme=self.mstis_scheme,
            descriptions=minus_move_descriptions
        )
        self.mstis_minus_flux = MinusMoveFlux(self.mstis_scheme)

    def _make_fake_minus_steps(self, scheme, descriptions):
        network = scheme.network
        state_adjustment = {
            self.state_A: lambda x: x,
            self.state_B: lambda x: 1.0 - x
        }

        minus_ensemble_to_mover = {m.minus_ensemble: m
                                   for m in scheme.movers['minus']}

        assert_equal(set(minus_ensemble_to_mover.keys()),
                     set(network.minus_ensembles))
        steps = []
        mccycle = 0
        for minus_traj in descriptions:
            for i, minus_ensemble in enumerate(network.minus_ensembles):
                replica = -1 - i
                adjustment = state_adjustment[minus_ensemble.state_vol]
                traj = make_1d_traj([adjustment(s) for s in minus_traj])
                assert_equal(minus_ensemble(traj), True)
                samp = paths.Sample(trajectory=traj,
                                    ensemble=minus_ensemble,
                                    replica=replica)
                sample_set = paths.SampleSet([samp])
                change = paths.AcceptedSampleMoveChange(
                    samples=[samp],
                    mover=minus_ensemble_to_mover[samp.ensemble],
                    details=paths.Details()
                )
                # NOTE: this makes it so that only one ensemble is
                # represented in the same set at any time, which isn't quite
                # how it actually works. However, this is doesn't matter for
                # the current implementation
                steps.append(paths.MCStep(mccycle=mccycle,
                                          active=sample_set,
                                          change=change))

                mccycle += 1
        assert_equal(len(steps), 4)
        return steps

    def test_get_minus_steps(self):
        all_mistis_steps = self.mistis_steps + self.mistis_minus_steps
        mistis_minus_steps = \
                self.mistis_minus_flux._get_minus_steps(all_mistis_steps)
        assert_equal(len(mistis_minus_steps), len(self.mistis_minus_steps))
        assert_items_equal(mistis_minus_steps, self.mistis_minus_steps)
        # this could be repeated for MSTIS, but why?

    def test_calculate(self):
        avg_t_in = (5.0 + 3.0) / 2
        avg_t_out = (2.0 + 5.0 + 3.0 + 3.0) / 4
        expected_flux = 1.0 / (avg_t_in + avg_t_out)

        mistis_flux = \
                self.mistis_minus_flux.calculate(self.mistis_minus_steps)
        for flux in mistis_flux.values():  # all values are the same
            assert_almost_equal(flux, expected_flux)

        mstis_flux = \
                self.mstis_minus_flux.calculate(self.mstis_minus_steps)
        for flux in mstis_flux.values():  # all values are the same
            assert_almost_equal(flux, expected_flux)

    @raises(ValueError)
    def test_bad_network(self):
        # raises error if more than one transition shares a minus ensemble
        # (flux cannot be calculated with multiple interface set minus move)
        state_C = paths.CVDefinedVolume(self.cv_x, 0.5, 0.7)
        trans_AB = self.mistis.transitions[(self.state_A, self.state_B)]
        trans_BA = self.mistis.transitions[(self.state_B, self.state_A)]
        interfaces_AB = trans_AB.interfaces
        interfaces_BA = trans_BA.interfaces
        interfaces_AC = trans_AB.interfaces
        bad_mistis = paths.MISTISNetwork([
            (self.state_A, interfaces_AB, self.state_B),
            (self.state_B, interfaces_BA, self.state_A),
            (self.state_A, interfaces_AC, state_C)
        ])
        scheme = paths.DefaultScheme(bad_mistis)
        scheme.build_move_decision_tree()
        minus_flux = MinusMoveFlux(scheme)


class TestPathLengthHistogrammer(TISAnalysisTester):
    def _check_network_results(self, network, hists):
        results = {0: {(3.0,): 2, (5.0,): 1, (7.0,): 1},
                   1: {(5.0,): 2, (7.0,): 1, (12.0,): 1},
                   2: {(7.0,): 2, (12.0,): 2}}

        ensembles_AB = self.sampling_ensembles_for_transition(network,
                                                              self.state_A,
                                                              self.state_B)
        ensembles_BA = self.sampling_ensembles_for_transition(network,
                                                              self.state_B,
                                                              self.state_A)
        for (key, dct) in results.iteritems():
            hist_dct_AB = hists[ensembles_AB[key]]._histogram
            assert_equal(dict(hist_dct_AB), dct)
            hist_dct_BA = hists[ensembles_BA[key]]._histogram
            assert_equal(dict(hist_dct_BA), dct)


    def test_calculate(self):
        default_histogrammer = \
                PathLengthHistogrammer(self.mistis.sampling_ensembles)
        assert_equal(default_histogrammer.hist_parameters,
                     {'bin_width': 5, 'bin_range': (0, 1000)})

        mistis_histogrammer = PathLengthHistogrammer(
            ensembles=self.mistis.sampling_ensembles,
            hist_parameters={'bin_width': 1, 'bin_range': (0, 10)}
        )
        mistis_hists = mistis_histogrammer.calculate(self.mistis_steps)
        self._check_network_results(self.mistis, mistis_hists)

        mstis_histogrammer = PathLengthHistogrammer(
            ensembles=self.mstis.sampling_ensembles,
            hist_parameters={'bin_width': 1, 'bin_range': (0, 10)}
        )
        mstis_hists = mstis_histogrammer.calculate(self.mstis_steps)
        self._check_network_results(self.mstis, mstis_hists)


class TestFullHistogramMaxLambda(TISAnalysisTester):
    def _check_transition_results(self, transition, hists):
        raw_lambda_results = {
            0: {-0.05: 0, 0.05: 2, 0.15: 1, 0.25: 1},
            1: {-0.05: 0, 0.05: 0, 0.15: 2, 0.25: 1, 0.35: 0, 1.05: 1},
            2: {-0.05: 0, 0.05: 0, 0.15: 0, 0.25: 2, 0.35: 0, 1.05: 2}
        }
        for (ens, result_dct) in raw_lambda_results.iteritems():
            hist = hists[transition.ensembles[ens]]()
            for key in result_dct.keys():
                assert_almost_equal(result_dct[key], hist(key))

    def test_calculate(self):
        mistis_AB = self.mistis.transitions[(self.state_A, self.state_B)]
        mistis_AB_histogrammer = FullHistogramMaxLambdas(
            transition=mistis_AB,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mistis_AB_hists = mistis_AB_histogrammer.calculate(self.mistis_steps)
        self._check_transition_results(mistis_AB, mistis_AB_hists)

        mistis_BA = self.mistis.transitions[(self.state_B, self.state_A)]
        mistis_BA_histogrammer = FullHistogramMaxLambdas(
            transition=mistis_BA,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mistis_BA_hists = mistis_BA_histogrammer.calculate(self.mistis_steps)
        self._check_transition_results(mistis_BA, mistis_BA_hists)

        mstis_AB = self.mstis.transitions[(self.state_A, self.state_B)]
        mstis_AB_histogrammer = FullHistogramMaxLambdas(
            transition=mstis_AB,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mstis_AB_hists = mstis_AB_histogrammer.calculate(self.mstis_steps)
        self._check_transition_results(mstis_AB, mstis_AB_hists)

        mstis_BA = self.mstis.transitions[(self.state_B, self.state_A)]
        mstis_BA_histogrammer = FullHistogramMaxLambdas(
            transition=mstis_BA,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mstis_BA_hists = mstis_BA_histogrammer.calculate(self.mstis_steps)
        self._check_transition_results(mstis_BA, mstis_BA_hists)


class TestConditionalTransitionProbability(TISAnalysisTester):
    def _check_network_results(self, network, ctp_results):
        results = {0: 0.0, 1: 0.25, 2: 0.5}
        ensembles_AB = self.sampling_ensembles_for_transition(network,
                                                              self.state_A,
                                                              self.state_B)
        ensembles_BA = self.sampling_ensembles_for_transition(network,
                                                              self.state_B,
                                                              self.state_A)

        for ens_num in range(len(ensembles_AB)):
            dct_AB = ctp_results[ensembles_AB[ens_num]]
            result = results[ens_num]
            if result != 0.0:
                assert_equal(dct_AB[self.state_B], result)
            if result != 1.0:
                assert_equal(dct_AB[self.state_A], 1.0-result)

        for ens_num in range(len(ensembles_BA)):
            dct_BA = ctp_results[ensembles_BA[ens_num]]
            result = results[ens_num]
            if result != 0.0:
                assert_equal(dct_BA[self.state_A], result)
            if result != 1.0:
                assert_equal(dct_BA[self.state_B], 1.0-result)


    def test_calculate(self):
        mistis_ctp_calc = ConditionalTransitionProbability(
            ensembles=self.mistis.sampling_ensembles,
            states=[self.state_A, self.state_B]
        )
        mistis_ctp = mistis_ctp_calc.calculate(self.mistis_steps)
        self._check_network_results(self.mistis, mistis_ctp)

        mstis_ctp_calc = ConditionalTransitionProbability(
            ensembles=self.mstis.sampling_ensembles,
            states=[self.state_A, self.state_B]
        )
        mstis_ctp = mstis_ctp_calc.calculate(self.mstis_steps)
        self._check_network_results(self.mstis, mstis_ctp)


class TestTotalCrossingProbability(TISAnalysisTester):
    def test_calculate(self):
        # a bit of integration test, until we make a MaxLambdaStub
        results = {0.0: 1.0, 0.1: 0.5, 0.2: 0.25, 0.3: 0.125,
                   0.5: 0.125, 1.0: 0.125}

        mistis_AB = self.mistis.transitions[(self.state_A, self.state_B)]
        mistis_AB_max_lambda = FullHistogramMaxLambdas(
            transition=mistis_AB,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mistis_AB_tcp = TotalCrossingProbability(mistis_AB_max_lambda)
        tcp_AB = mistis_AB_tcp.calculate(self.mistis_steps)
        for (x, result) in results.iteritems():
            assert_almost_equal(tcp_AB(x), result)

        mistis_BA = self.mistis.transitions[(self.state_B, self.state_A)]
        mistis_BA_max_lambda = FullHistogramMaxLambdas(
            transition=mistis_BA,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mistis_BA_tcp = TotalCrossingProbability(mistis_BA_max_lambda)
        tcp_BA = mistis_BA_tcp.calculate(self.mistis_steps)
        for (x, result) in results.iteritems():
            assert_almost_equal(tcp_AB(x), result)

        mstis_AB = self.mstis.transitions[(self.state_A, self.state_B)]
        mstis_AB_max_lambda = FullHistogramMaxLambdas(
            transition=mstis_AB,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mstis_AB_tcp = TotalCrossingProbability(mstis_AB_max_lambda)
        tcp_AB = mstis_AB_tcp.calculate(self.mstis_steps)
        for (x, result) in results.iteritems():
            assert_almost_equal(tcp_AB(x), result)

        mstis_BA = self.mstis.transitions[(self.state_B, self.state_A)]
        mstis_BA_max_lambda = FullHistogramMaxLambdas(
            transition=mstis_BA,
            hist_parameters={'bin_width': 0.1, 'bin_range': (-0.1, 1.1)}
        )
        mstis_BA_tcp = TotalCrossingProbability(mstis_BA_max_lambda)
        tcp_BA = mstis_BA_tcp.calculate(self.mstis_steps)
        for (x, result) in results.iteritems():
            assert_almost_equal(tcp_AB(x), result)


class TestStandardTransitionProbability(TISAnalysisTester):
    pass

class TestTransitionDictResults(TISAnalysisTester):
    pass


class TestTISAnalysis(TISAnalysisTester):
    pass

class TestStandardTISAnalysis(TISAnalysisTester):
    pass