from openpathsampling.netcdfplus import DelayedLoader
from numpydoctools import NumpyDocTools


def attach_features(features, use_lazy_reversed=False):
    """
    Select snapshot features
    """

    # create a parser that can combine numpy docstrings
    parser = NumpyDocTools()

    ADD_SOURCE_CODE = True

    def _decorator(cls):
        """
        Class decorator that will attach function for compiled features

        This function will use a list of features and create `__init__` and
        copy functions based on the structure of features for performance.

        It will also take care of creating a joined docstring and the corect
        signature of the `__init__` function

        A attribute `__features__` will be added that contains information
        about the used features their structure. It is a dictionary with the
        following keys

        classes : dict of used features
        lazy : dict of string
            names of features that are treated as lazy loaded object
        properties : dict of string
            names of features that are treated as properties
        lazy : dict of string
            names of features that are treated as lazy loaded object
        reversal : dict of string
            names of features that are treated as being reversible
        minus : dict of string
            names of features that are treated as being reversible and
            should be multiplied by -1.0
        flip : dict of string
            names of features that are treated as being reversible and
            should be negated `~`
        attributes : dict of string
            names of features that are treated as being class attributes
        parameters : dict of string
            names of features that attributes but not properties and hence
            possible parameters for creation
        numpy : dict of string
            names of features that can use numpy for faster copying, etc.

        Parameters
        ----------
        cls : the `class` to the modified

        Returns
        -------
        class
            the modified class

        """

        # important for compile to work properly
        import openpathsampling as paths
        import numpy as np

        parser.clear()

        # create and fill `__features__` with values from feature structures
        if hasattr(cls, '__features__'):
            __features__ = cls.__features__
        else:
            __features__ = dict()

        for name in ['attributes', 'minus', 'reversal', 'properties',
                     'flip', 'numpy', 'lazy', 'required', 'classes']:
            if name not in __features__:
                __features__[name] = []

        if ADD_SOURCE_CODE:
            if 'debug' not in __features__:
                __features__['debug'] = {}

        __features__['classes'] += features

        if use_lazy_reversed:
            cls._reversed = DelayedLoader()
            # if '_reversed' not in __features__['lazy']:
            #     __features__['lazy'] += ['_reversed']
            #
        origin = dict()
        required = dict()
        # loop over all the features
        for feature in features:

            # add properties
            for prop in feature.attributes:
                if hasattr(feature, prop) and callable(getattr(feature, prop)):
                    __features__['properties'] += [prop]
                    setattr(cls, prop, property(getattr(feature, prop)))

            # copy specific attribute types
            for name in ['attributes', 'minus', 'lazy', 'flip', 'numpy', 'required']:
                if hasattr(feature, name):
                    content = getattr(feature, name)
                    if type(content) is str:
                        content = [content]

                    if name == 'attributes':
                        for c in content:
                            if c in __features__['attributes']:
                                raise RuntimeError((
                                    'Feature collision. Attribute "%s" present in two features. ' +
                                    'Please remove one feature "%s" or "%s"') %
                                    (c, str(feature), str(origin[c])))

                    for c in content:
                        origin[c] = feature

                    __features__[name] += content

        for name in __features__['required']:
            if name not in __features__['attributes']:
                raise RuntimeError((
                    'Attribute "%s" is required, but only "%s" found. Please make sure ' +
                    'that is will be added by ' +
                    'some feature') % (name, str(__features__['attributes']))
                )

        __features__['reversal'] = [
            attr for attr in __features__['attributes']
            if attr not in __features__['minus']
            and attr not in __features__['properties']
            and attr not in __features__['flip']
        ]

        __features__['parameters'] = [
            attr for attr in __features__['attributes']
            if attr not in __features__['properties']
        ]

        has_lazy = bool(__features__['lazy']) or use_lazy_reversed

        # add descriptors that can handle lazy loaded objects
        for attr in __features__['lazy']:
            setattr(cls, attr, DelayedLoader())

        # update the docstring to be a union of docstrings from the class
        # and the features

        # get docstring from class
        parser.add_docs_from(cls)

        # from top of features
        for feat in __features__['classes']:
            parser.add_docs_from(feat)

            # from properties
            for prop in __features__['properties']:
                if hasattr(feat, prop):
                    if prop not in parser.attributes:
                        parser.add_docs_from(
                            getattr(feat, prop),
                            keep_only=['attributes'],
                            translate={'returns': 'attributes'}
                        )

        # set new docstring. This is only possible since our class is created
        # using a Metaclass for abstract classes `abc`. Normal classes cannot
        # have thier docstring changed.
        cls.__doc__ = parser.get_docstring()

        # compile the function for .copy()

        # def copy(self):
        #     this = cls.__new__(cls)
        #     this._lazy = { ... }
        #     this.feature1 = self.feature1

        code = []
        code += [
            "def copy(self):",
            "    this = cls.__new__(cls)",
        ]

        if has_lazy:
            code += [
                "    this._lazy = {",
            ]
            code += [
                "       cls.{0} : self._lazy[cls.{0}],".format(lazy)
                for lazy in __features__['lazy']
            ]
            code += [
                "    }"
            ]

        code += [
            "    this._reversed = None"
        ]

        code += map(
            "    this.{0} = self.{0}".format,
            filter(
                lambda x : x not in __features__['lazy'],
                __features__['parameters']
            )
        )

        code += [
            "    return this"
        ]

        # compile the code and register the new function
        try:
            source_code = '\n'.join(code)
            cc = compile(source_code, '<string>', 'exec')
            exec cc in locals()

            if ADD_SOURCE_CODE:
                __features__['debug']['copy'] = source_code

            cls.copy = copy

        except RuntimeError as e:
            print e
            pass

        # compile the function for .copy_to(target)

        # def copy_to(self, target):
        #     this = target
        #     this._lazy = { ... }
        #     this.feature1 = self.feature1
        #     return this

        code = []
        code += [
            "def copy_to(self, target):",
        ]

        if has_lazy:
            code += [
                "    target._lazy = {",
            ]
            code += [
                "       cls.{0} : self._lazy[cls.{0}],".format(lazy)
                for lazy in __features__['lazy']
            ]
            code += [
                "    }"
            ]

        code += [
            "    target._reversed = None"
        ]

        code += map(
            "    np.copyto(target.{0}, self.{0})".format,
            filter(
                lambda x : x not in __features__['lazy'] and x in __features__['numpy'],
                __features__['parameters']
            )
        )
        code += map(
            "    target.{0} = self.{0}".format,
            filter(
                lambda x : x not in __features__['lazy'] and x not in __features__['numpy'],
                __features__['parameters']
            )
        )

        # compile the code and register the new function
        try:
            source_code = '\n'.join(code)
            cc = compile(source_code, '<string>', 'exec')
            exec cc in locals()

            if ADD_SOURCE_CODE:
                __features__['debug']['copy_to'] = source_code

            cls.copy_to = copy_to

        except RuntimeError as e:
            print e
            pass

        # compile the function for .create_reversed()

        # def create_reversed(self):
        #     this = cls.__new__(cls)
        #     this._lazy = { ... }
        #     this.feature1 = self.feature1
        #     this.feature2 = - self.feature2  # minus feature
        #     this.feature3 = ~ self.feature3  # flip features
        #     return this

        code = []
        code += [
            "def create_reversed(self):",
            "    this = cls.__new__(cls)"
        ]

        if has_lazy:
            code += [
                "    this._lazy = {",
            ]
            code += [
                "       cls.{0} : self._lazy[cls.{0}],".format(lazy)
                for lazy in __features__['lazy']
            ]

            code += [
                "    }"
            ]

        code += [
            "    this._reversed = self"
        ]

        code += map(
            "    this.{0} = self.{0}".format,
            filter(
                lambda x : x not in __features__['lazy'],
                __features__['reversal']
            )
        )
        code += map("    this.{0} = - self.{0}".format,
            filter(
                lambda x : x not in __features__['lazy'],
                __features__['minus']
            )
        )

        code += map("    this.{0} = ~ self.{0}".format,
            filter(
                lambda x : x not in __features__['lazy'],
                __features__['flip']
            )
        )

        code += [
            "    return this"
        ]

        # compile the code and register the new function
        try:
            source_code = '\n'.join(code)
            cc = compile(source_code, '<string>', 'exec')
            exec cc in locals()

            if ADD_SOURCE_CODE:
                __features__['debug']['create_reversed'] = source_code


            cls.create_reversed = create_reversed

        except RuntimeError as e:
            print e
            pass

        # compile the function for __init__

        # def __init__(self, attribute1=None, ... ):
        #     self._lazy = { ... }
        #     self.feature1 = self.feature1
        #     return this

        # we use as signature all feature names in parameters
        parameters = []
        for feat in __features__['parameters']:
            if feat in __features__['flip']:
                parameters += ['{0}=False'.format(feat)]
            else:
                parameters += ['{0}=None'.format(feat)]

        code = []

        if parameters:
            signature = ', ' + ', '.join(parameters)
        else:
            signature = ''

        code += [
            "def __init__(self%s):" % signature,
        ]

        # dict for lazy attributes using DelayedLoader descriptor
        if has_lazy:
            code += [
                "    self._lazy = {",
            ]
            code += [
                "       cls.{0} : {0},".format(lazy)
                for lazy in __features__['lazy']
            ]
            code += [
                "    }"
            ]

        # set _reversed
        code += [
            "    self._reversed = None"
        ]

        # set non-lazy attributes
        code += map(
            "    self.{0} = {0}".format,
            filter(
                lambda x : x not in __features__['lazy'],
                __features__['parameters']
            )
        )

        # compile the code and register the new function
        try:
            source_code = '\n'.join(code)
            cc = compile(source_code, '<string>', 'exec')
            exec cc in locals()

            if ADD_SOURCE_CODE:
                __features__['debug']['__init__'] = source_code

            cls.__init__ = __init__

        except RuntimeError as e:
            print e
            pass

        # compile the function for __init__

        # def init_empty(self)):
        #     self._lazy = {}
        #     self._reversed = None
        #     return this

        code = []
        code += [
            "def init_empty(self):",
        ]

        # dict for lazy attributes using DelayedLoader descriptor
        if has_lazy:
            code += [
                "    self._lazy = {}",
            ]

        # set _reversed
        code += [
            "    self._reversed = None"
        ]

        # compile the code and register the new function
        try:
            source_code = '\n'.join(code)
            cc = compile(source_code, '<string>', 'exec')
            exec cc in locals()

            if ADD_SOURCE_CODE:
                __features__['debug']['init_empty'] = source_code

            cls.init_empty = init_empty

        except RuntimeError as e:
            print e
            pass

        code = []
        code += [ "@staticmethod" ]
        code += [
            "def init_copy(self%s):" % signature,
        ]

        if has_lazy:
            code += [
                "    self._lazy = {",
            ]
            code += [
                "       cls.{0} : {0},".format(lazy)
                for lazy in __features__['parameters']
                if lazy in __features__['lazy']
            ]
            code += [
                "    }"
            ]

        code += [
            "    self._reversed = None"
        ]

        code += map(
            "    self.{0} = {0}".format,
            [
                feat for feat in __features__['parameters'] if
                feat not in __features__['numpy'] and
                feat not in __features__['lazy']
            ])

        code += map(
            "    np.copyto(self.{0}, {0})".format,
            [
                feat for feat in __features__['parameters'] if
                feat in __features__['numpy'] and
                feat not in __features__['lazy']
            ])

        # compile the code and register the new function
        try:
            source_code = '\n'.join(code)
            cc = compile(source_code, '<string>', 'exec')
            exec cc in locals()

            if ADD_SOURCE_CODE:
                __features__['debug']['init_copy'] = source_code

            cls.init_copy = init_copy

        except RuntimeError as e:
            print e
            pass

        cls.__features__ = __features__

        return cls

    return _decorator