'''
Created on 03.09.2014

@author: Jan-Hendrik Prinz, David W.H. Swenson
'''

import range_logic
from openpathsampling.todict import restores_as_full_object

@restores_as_full_object
class Volume(object):
    """
    A Volume describes a set of snapshots 
    """
    def __call__(self, snapshot):
        '''
        Returns `True` if the given snapshot is part of the defined Region
        '''
        
        return False # pragma: no cover
                
    def __str__(self):
        '''
        Returns a string representation of the volume
        '''
        return 'volume' # pragma: no cover

    def __or__(self, other):
        if self is other:
            return self
        elif type(other) is EmptyVolume:
            return self
        elif type(other) is FullVolume:
            return other
        else:
            return OrVolume(self, other)

    def __xor__(self, other):
        if self is other:
            return EmptyVolume()
        elif type(other) is EmptyVolume:
            return self
        elif type(other) is FullVolume:
            return ~ self
        else:
            return XorVolume(self, other)

    def __and__(self, other):
        if self is other:
            return self
        elif type(other) is EmptyVolume:
            return other
        elif type(other) is FullVolume:
            return self
        else:
            return AndVolume(self, other)

    def __sub__(self, other):
        if self is other:
            return EmptyVolume()
        elif type(other) is EmptyVolume:
            return self
        elif type(other) is FullVolume:
            return EmptyVolume()
        else:
            return SubVolume(self, other)
        
    def __invert__(self):
        return NegatedVolume(self)

    def __eq__(self, other):
        return str(self) == str(other)

@restores_as_full_object
class VolumeCombination(Volume):
    """
    Logical combination of volumes. 

    This should be treated as an abstract class. For storage purposes, use
    specific subclasses in practice.
    """
    def __init__(self, volume1, volume2, fnc, str_fnc):
        super(VolumeCombination, self).__init__()
        self.volume1 = volume1
        self.volume2 = volume2
        self.fnc = fnc
        self.sfnc = str_fnc

    def __call__(self, snapshot):
        return self.fnc(self.volume1.__call__(snapshot), self.volume2.__call__(snapshot))
    
    def __str__(self):
        return '(' + self.sfnc.format(str(self.volume1), str(self.volume2)) + ')'

    def to_dict(self):
        return { 'volume1' : self.volume1, 'volume2' : self.volume2 }

@restores_as_full_object
class OrVolume(VolumeCombination):
    """ "Or" combination (union) of two volumes."""
    def __init__(self, volume1, volume2):
        super(OrVolume, self).__init__(volume1, volume2, lambda a,b : a or b, str_fnc = '{0} or {1}')

@restores_as_full_object
class AndVolume(VolumeCombination):
    """ "And" combination (intersection) of two volumes."""
    def __init__(self, volume1, volume2):
        super(AndVolume, self).__init__(volume1, volume2, lambda a,b : a and b, str_fnc = '{0} and {1}')

@restores_as_full_object
class XorVolume(VolumeCombination):
    """ "Xor" combination of two volumes."""
    def __init__(self, volume1, volume2):
        super(XorVolume, self).__init__(volume1, volume2, lambda a,b : a ^ b, str_fnc = '{0} xor {1}')

@restores_as_full_object
class SubVolume(VolumeCombination):
    """ "Subtraction" combination (relative complement) of two volumes."""
    def __init__(self, volume1, volume2):
        super(SubVolume, self).__init__(volume1, volume2, lambda a,b : a and not b, str_fnc = '{0} and not {1}')


@restores_as_full_object
class NegatedVolume(Volume):
    """Negation (logical not) of a volume."""
    def __init__(self, volume):
        super(NegatedVolume, self).__init__()
        self.volume = volume

    def __call__(self, snapshot):
        return not self.volume(snapshot)
    
    def __str__(self):
        return '(not ' + str(self.volume) + ')'
    
@restores_as_full_object
class EmptyVolume(Volume):
    """Empty volume: no snapshot can satisfy"""
    def __init__(self):
        super(EmptyVolume, self).__init__()

    def __call__(self, snapshot):
        return False

    def __and__(self, other):
        return self

    def __or__(self, other):
        return other

    def __xor__(self, other):
        return other

    def __sub__(self, other):
        return self

    def __invert__(self):
        return FullVolume()

    def __str__(self):
        return 'empty'

@restores_as_full_object
class FullVolume(Volume):
    """Volume which all snapshots can satisfy."""
    def __init__(self):
        super(FullVolume, self).__init__()

    def __call__(self, snapshot):
        return True

    def __invert__(self):
        return EmptyVolume()

    def __and__(self, other):
        return other

    def __or__(self, other):
        return self

    def __xor__(self, other):
        return ~ other

    def __sub__(self, other):
        return ~ other

    def __str__(self):
        return 'all'

@restores_as_full_object
class LambdaVolume(Volume):
    """
    Volume defined by a range of a collective variable `orderparameter`.

    Contains all snapshots `snap` for which `lamba_min <
    orderparameter(snap)` and `lambda_max > orderparameter(snap)`.
    """
    def __init__(self, orderparameter, lambda_min = 0.0, lambda_max = 1.0):
        '''
        Attributes
        ----------
        orderparameter : OrderParameter
            the orderparameter object
        lambda_min : float
            the minimal allowed orderparameter
        lambda_max: float
            the maximal allowed orderparameter
        '''
        super(LambdaVolume, self).__init__()
        self.orderparameter = orderparameter
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        
    # Typically, the logical combinations are only done once. Because of
    # this, it is worth passing these through a check to speed up the logic.

    # To get all the usefulness of the range logic in a subclass, all you
    # should need to override is _copy_with_new_range (so that it inits any
    # extra info the subclass carries) and range_and/or/sub, so that they
    # return the correct behavior for the new subclass. Everything else
    # comes for free.
    def _copy_with_new_range(self, lmin, lmax):
        """Shortcut to make a LambdaVolume with all parameters the same as
        this one except the range. This is useful for the range logic when
        dealing with subclasses: just override this function to copy extra
        information.
        """
        return LambdaVolume(self.orderparameter, lmin, lmax)

    @staticmethod
    def range_and(amin, amax, bmin, bmax):
        return range_logic.range_and(amin, amax, bmin, bmax)
    @staticmethod
    def range_or(amin, amax, bmin, bmax):
        return range_logic.range_or(amin, amax, bmin, bmax)
    @staticmethod
    def range_sub(amin, amax, bmin, bmax):
        return range_logic.range_sub(amin, amax, bmin, bmax)

    def _lrange_to_Volume(self, lrange):
        """Takes results from one of the range_logic functions and returns
        the appropriate Volume.

        Parameters
        ----------
        lrange : None or 1 or list of 2-tuples
            Key to the volume to be returned: None returns the EmptyVolume, 1
            returns self, and a list of 2-tuples is __or__'d as (min,max) to
            make a VolumeCombinations

        Returns
        -------
        Volume
            appriate volume according to lrange

        Raises
        ------
        ValueError
            if the input lrange is not an allowed value
        """
        if lrange == None:
            return EmptyVolume()
        elif lrange == 1:
            return self
        elif lrange == -1:
            return FullVolume()
        elif len(lrange) == 1:
            return self._copy_with_new_range(lrange[0][0], lrange[0][1])
        elif len(lrange) == 2:
            return OrVolume(
                self._copy_with_new_range(lrange[0][0], lrange[0][1]),
                self._copy_with_new_range(lrange[1][0], lrange[1][1])
            )
        else:
            raise ValueError(
                "lrange value not understood: {0}".format(lrange)
            ) # pragma: no cover

    def __and__(self, other):
        if (type(other) is type(self) and 
                self.orderparameter == other.orderparameter):
            lminmax = self.range_and(self.lambda_min, self.lambda_max,
                                other.lambda_min, other.lambda_max)
            return self._lrange_to_Volume(lminmax)
        else:
            return super(LambdaVolume, self).__and__(other)

    def __or__(self, other):
        if (type(other) is type(self) and 
                self.orderparameter == other.orderparameter):
            lminmax = self.range_or(self.lambda_min, self.lambda_max,
                               other.lambda_min, other.lambda_max)
            return self._lrange_to_Volume(lminmax)
        else:
            return super(LambdaVolume, self).__or__(other)

    def __xor__(self, other):
        if (type(other) is type(self) and 
                self.orderparameter == other.orderparameter):
            # taking the shortcut here
            return ((self | other) - (self & other))
        else:
            return super(LambdaVolume, self).__xor__(other)

    def __sub__(self, other):
        if (type(other) is type(self) and 
                self.orderparameter == other.orderparameter):
            lminmax = self.range_sub(self.lambda_min, self.lambda_max,
                            other.lambda_min, other.lambda_max)
            return self._lrange_to_Volume(lminmax)
        else:
            return super(LambdaVolume, self).__sub__(other)

    def __call__(self, snapshot):
        l = self.orderparameter(snapshot)
        return l >= self.lambda_min and l <= self.lambda_max

    def __str__(self):
        return '{{x|{2}(x) in [{0}, {1}]}}'.format( self.lambda_min, self.lambda_max, self.orderparameter.name)

@restores_as_full_object
class LambdaVolumePeriodic(LambdaVolume):
    """
    As with `LambdaVolume`, but for a periodic order parameter.

    Defines a Volume containing all states where orderparameter, a periodic
    function wrapping into the range [period_min, period_max], is in the
    given range [lambda_min, lambda_max].

    Attributes
    ----------
    period_min : float (optional)
        minimum of the periodic domain
    period_max : float (optional)
        maximum of the periodic domain
    """

    _excluded_attr = ['wrap']
    def __init__(self, orderparameter, lambda_min = 0.0, lambda_max = 1.0,
                                       period_min = None, period_max = None):
        super(LambdaVolumePeriodic, self).__init__(orderparameter,
                                                    lambda_min, lambda_max)        
        self.period_min = period_min
        self.period_max = period_max
        if (period_min is not None) and (period_max is not None):
            self._period_shift = period_min
            self._period_len = period_max - period_min
            if self.lambda_max - self.lambda_min > self._period_len:
                raise Exception("Range of volume larger than periodic bounds.")
            elif self.lambda_max-self.lambda_min == self._period_len:
                self.lambda_min = period_min
                self.lambda_max = period_max
            else:
                self.lambda_min = self.do_wrap(lambda_min)
                self.lambda_max = self.do_wrap(lambda_max)
            self.wrap = True
        else:
            self.wrap = False

    def do_wrap(self, value):
        """Wraps `value` into the periodic domain."""
        return ((value-self._period_shift) % self._period_len) + self._period_shift

    # next few functions add support for range logic
    def _copy_with_new_range(self, lmin, lmax):
        return LambdaVolumePeriodic(self.orderparameter, lmin, lmax,
                                    self.period_min, self.period_max)

    @staticmethod
    def range_and(amin, amax, bmin, bmax):
        return range_logic.periodic_range_and(amin, amax, bmin, bmax)
    @staticmethod
    def range_or(amin, amax, bmin, bmax):
        return range_logic.periodic_range_or(amin, amax, bmin, bmax)
    @staticmethod
    def range_sub(amin, amax, bmin, bmax):
        return range_logic.periodic_range_sub(amin, amax, bmin, bmax)


    def __invert__(self):
        # consists of swapping max and min
        return LambdaVolumePeriodic(self.orderparameter,
                                    self.lambda_max, self.lambda_min,
                                    self.period_min, self.period_max
                                   )

    def __call__(self, snapshot):
        l = self.orderparameter(snapshot)
        if self.wrap:
            l = self.do_wrap(l)
        if self.lambda_min > self.lambda_max:
            return l >= self.lambda_min or l <= self.lambda_max
        else:
            return l >= self.lambda_min and l <= self.lambda_max

    def __str__(self):
        if self.wrap:
            fcn = 'x|({0}(x) - {2}) % {1} + {2}'.format(
                        self.orderparameter.name,
                        self._period_len, self._period_shift)
            if self.lambda_min < self.lambda_max:
                domain = '[{0}, {1}]'.format(
                        self.lambda_min, self.lambda_max)
            else:
                domain = '[{0}, {1}] union [{2}, {3}]'.format(
                        self._period_shift, self.lambda_max,
                        self.lambda_min, self._period_shift+self._period_len)
            return '{'+fcn+' in '+domain+'}'
        else:
            return '{{x|{2}(x) [periodic] in [{0}, {1}]}}'.format( 
                        self.lambda_min, self.lambda_max, 
                        self.orderparameter.name)


class VolumeFactory(object):
    @staticmethod
    def _check_minmax(minvals, maxvals):
        # if one is an integer, convert it to a list
        if type(minvals) == int or type(minvals) == float:
            if type(maxvals) == list:
                minvals = [minvals]*len(maxvals)
            else:
                raise ValueError("minvals is a scalar; maxvals is not a list")
        elif type(maxvals) == int or type(maxvals) == float:
            if type(minvals) == list:
                maxvals = [maxvals]*len(minvals)
            else:
                raise ValueError("maxvals is a scalar; minvals is not a list")

        if len(minvals) != len(maxvals):
            raise ValueError("len(minvals) != len(maxvals)")
        return (minvals, maxvals)

    @staticmethod
    def LambdaVolumeSet(op, minvals, maxvals):
        minvals, maxvals = VolumeFactory._check_minmax(minvals, maxvals)
        myset = []
        for i in range(len(maxvals)):
            myset.append(LambdaVolume(op, minvals[i], maxvals[i]))
        return myset

    @staticmethod
    def LambdaVolumePeriodicSet(op, minvals, maxvals, 
                                period_min=None, period_max=None):
        minvals, maxvals = VolumeFactory._check_minmax(minvals, maxvals)
        myset = []
        for i in range(len(maxvals)):
            myset.append(LambdaVolumePeriodic(op, minvals[i], maxvals[i], 
                                              period_min, period_max))
        return myset
