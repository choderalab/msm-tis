import base64
import json
import numpy as np
from simtk import unit as units
import yaml
import openpathsampling as paths
import inspect

import logging
logger = logging.getLogger(__name__)

class OPSObject(object):
    """Mixin that allows an object to carry a .name property that can be saved

    It is not allowed to rename object once it has been given a name. Also
    storage usually sets the name to empty if an object has not been named
    before. This means that you cannot name an object, after is has been saved.
    """

    @staticmethod
    def _subclasses(cls):
        return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                       for g in OPSObject._subclasses(s)]

    @staticmethod
    def objects():
        """
        Returns a dictionary of all subclasses
        """
        subclasses = OPSObject._subclasses(OPSObject)

        return { subclass.__name__ : subclass for subclass in subclasses }

    @classmethod
    def args(cls):
        try:
            args = inspect.getargspec(cls.__init__)
        except TypeError:
            return []
        return args[0]

    _excluded_attr = []
    _exclude_private_attr = True
    _restore_non_initial_attr = True
    _restore_name = True

    def to_dict(self):
        excluded_keys = ['idx', 'json', 'identifier']
        return {
            key: value for key, value in self.__dict__.iteritems()
            if key not in excluded_keys
            and key not in self._excluded_attr
            and not (key.startswith('_') and self._exclude_private_attr)
        }

    @classmethod
    def from_dict(cls, dct):
        if dct is None:
            dct = {}
        try:
            init_dct = dct
            non_init_dct = {}
            if hasattr(cls, 'args'):
                args = cls.args()
                init_dct = {key: dct[key] for key in dct if key in args}
                non_init_dct = {key: dct[key] for key in dct if key not in args}

            obj = cls(**init_dct)

            if cls._restore_non_initial_attr:
                if len(non_init_dct) > 0:
                    for key, value in non_init_dct.iteritems():
                        setattr(obj, key, value)
            else:
                if cls._restore_name:
                    if 'name' in dct:
                        obj.name = dct['name']

        except TypeError as e:
            print dct
            print cls.__name__
            print e
            print args
            print init_dct
            print non_init_dct

        return obj

class OPSNamed(OPSObject):
    """Mixin that allows an object to carry a .name property that can be saved

    It is not allowed to rename object once it has been given a name. Also
    storage usually sets the name to empty if an object has not been named
    before. This means that you cannot name an object, after is has been saved.
    """

    def __init__(self):
        super(OPSNamed, self).__init__()
        self._name = ''
        self._name_fixed = False

    @property
    def default_name(self):
        return '[' + self.__class__.__name__ + ']'

    def fix_name(self):
        self._name_fixed = True

    @property
    def name(self):
        if self._name == '':
            return self.default_name
        else:
            return self._name

    @name.setter
    def name(self, name):
        if self._name_fixed:
            raise ValueError('Objects cannot be renamed to "%s" after is has been saved, it is already named "%s"' % ( name, self._name))
        else:
            self._name = name

    def named(self, name):
        """Set the name

        This is only for syntactic sugar and allow for chained generation

        Example
        -------
        >>> import openpathsampling as p
        >>> full = p.FullVolume().named('myFullVolume')
        """
#        copied_object = copy.copy(self)
#        copied_object._name = name
#        if hasattr(copied_object, 'idx'):
#            copied_object.idx = dict()

        self._name = name

        return self

class ObjectJSON(object):
    """
    A simple implementation of a pickle algorithm to create object that can be converted to json and back
    """

    allow_marshal = True

    def __init__(self, unit_system = None):
        self.excluded_keys = []
        self.unit_system = unit_system
        self.class_list = paths.OPSNamed.objects()

    def simplify_object(self, obj, base_type = ''):
        return { '_cls' : obj.__class__.__name__, '_dict' : self.simplify(obj.to_dict(), obj.base_cls_name) }

    def simplify(self, obj, base_type = ''):
        if type(obj).__module__ != '__builtin__':
            if type(obj) is units.Quantity:
                # This is number with a unit so turn it into a list
                if self.unit_system is not None:
                    return { '_value' : obj.value_in_unit_system(self.unit_system), '_units' : self.unit_to_dict(obj.unit.in_unit_system(self.unit_system)) }
                else:
                    return { '_value' : obj / obj.unit, '_units' : self.unit_to_dict(obj.unit) }
            elif type(obj) is np.ndarray:
                # this is maybe not the best way to store large numpy arrays!
                return { '_numpy' : self.simplify(obj.shape), '_dtype' : str(obj.dtype), '_data' : base64.b64encode(obj) }
            elif hasattr(obj, 'to_dict'):
                # the object knows how to dismantle itself into a json string so use this
                return { '_cls' : obj.__class__.__name__, '_dict' : self.simplify(obj.to_dict(), base_type) }
            else:
                return None
        elif type(obj) is list:
            return [self.simplify(o, base_type) for o in obj]
        elif type(obj) is tuple:
            return { '_tuple' : [self.simplify(o, base_type) for o in obj] }
        elif type(obj) is dict:
            ### we want to support storable objects as keys so we need to wrap
            ### dicts with care and store them using tuples

            simple = [ key for key in obj.keys() if type(key) is str or type(key) is int ]

            if len(simple) < len(obj):
                # other keys than int or str
                result = { '_dict' : [
                    self.simplify(tuple([key, o]))
                    for key, o in obj.iteritems()
                    if key not in self.excluded_keys
                ]}

            else:
                # simple enough, do it the old way
                # FASTER VERSION NORMALLY
                result = { key : self.simplify(o)
                    for key, o in obj.iteritems()
                    if key not in self.excluded_keys
                }

                # SLOWER VERSION FOR DEBUGGING
                #result = {}
                #for key, o in obj.iteritems():
                    #logger.debug("Making dict entry of " + str(key) + " : "
                                 #+ str(o))
                    #if key not in self.excluded_keys:
                        #result[key] = self.simplify(o)
                    #else:
                        #logger.debug("EXCLUDED")

            return result
        elif type(obj) is slice:
            return { '_slice' : [obj.start, obj.stop, obj.step]}
        else:
            oo = obj
            return oo

    def build(self,obj):
        global class_list
        if type(obj) is dict:
            if '_units' in obj and '_value' in obj:
                return obj['_value'] * self.unit_from_dict(obj['_units'])
            elif '_slice' in obj:
                return slice(*obj['_slice'])
            elif '_numpy' in obj:
                return np.frombuffer(base64.decodestring(obj['_data']), dtype=np.dtype(obj['_dtype'])).reshape(self.build(obj['_numpy']))
            elif '_cls' in obj and '_dict' in obj:
                if obj['_cls'] in self.class_list:
                    attributes = self.build(obj['_dict'])
                    return self.class_list[obj['_cls']].from_dict(attributes)
                else:
                    raise ValueError('Cannot create obj of class "' + obj['_cls']+ '". Class is not registered as creatable!')
            elif '_tuple' in obj:
                return tuple([self.build(o) for o in obj['_tuple']])
            elif '_dict' in obj:
                return {
                    self.build(key) : self.build(o)
                    for key, o in self.build(obj['_dict'])
                }
            else:
                return {
                    key : self.build(o)
                    for key, o in obj.iteritems()
                }
        elif type(obj) is list:
            return [self.build(o) for o in obj]
        else:
            return obj

    def unitsytem_to_list(self, unit_system):
        """
        Turn a simtk.UnitSystem() into a list of strings representing the unitsystem for serialization
        """
        return [ u.name  for u in unit_system.units ]

    def unit_system_from_list(self, unit_system_list):
        """
        Create a simtk.UnitSystem() from a serialialized list of strings representing the unitsystem
        """
        return units.UnitSystem([ getattr(units, unit_name).iter_base_or_scaled_units().next()[0] for unit_name in unit_system_list])

    def unit_to_symbol(self, unit):
        return str(1.0 * unit).split()[1]

    def unit_to_dict(self, unit):
        unit_dict = {p.name : int(fac) for p, fac in unit.iter_base_or_scaled_units()}
        return unit_dict

    def unit_from_dict(self, unit_dict):
        unit = units.Unit({})
        for unit_name, unit_multiplication in unit_dict.iteritems():
            unit *= getattr(units, unit_name)**unit_multiplication

        return unit

    def to_json(self, obj, base_type = ''):
        simplified = self.simplify(obj, base_type)
        return json.dumps(simplified)

    def to_json_object(self, obj, base_type = ''):
        simplified = self.simplify_object(obj, base_type)
        try:
            json_str = json.dumps(simplified)
        except TypeError:
            print obj.__class__.__name__
            print obj.__dict__
            print simplified
            raise ValueError('Not possible to turn object into json')

        return json_str

    def from_json(self, json_string):
        simplified = yaml.load(json_string)
        return self.build(simplified)

    def unit_to_json(self, unit):
        simple = self.unit_to_dict(unit)
        return self.to_json(simple)

    def unit_from_json(self, json_string):
        return self.unit_from_dict(self.from_json(json_string))
