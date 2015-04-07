from object_storage_with_lazyloading import ObjectStorage
from openpathsampling.dynamics.dynamics_engine import DynamicsEngine

class DynamicsEngineStorage(ObjectStorage):

    def __init__(self, storage):
        super(DynamicsEngineStorage, self).__init__(storage, DynamicsEngine, named=True)

    #TODO: Simplify to use new object storage. Might want to add a from_dict function that does just that

    def load(self, idx, lazy=True):
        '''
        Returns an object from the storage. Needs to be implented from the specific storage class.
        '''

        # Create object first to break any unwanted recursion in loading
        engine_type = self.storage.variables['dynamicsengine_type'][int(idx)]

        # try to create an object of the same type as the original

        engine_class_dict = DynamicsEngine.__descendents__()
        options = self.simplifier.from_json(self.storage.variables['dynamicsengine_options'][int(idx)])
        engine = engine_class_dict[engine_type](options=options)

        return engine

    def save(self, engine, idx=None):
        '''
        Returns an object from the storage. Needs to be implemented from the specific storage class.
        '''

        self.storage.variables['dynamicsengine_type'][int(idx)] = engine.__class__.__name__

        if self.named and hasattr(engine, 'name'):
            self.storage.variables[self.db + '_uid'][idx] = engine.name

        self.storage.variables['dynamicsengine_options'][int(idx)] = self.simplifier.to_json(engine.options)

    def _init(self):
        """
        Initialize the associated storage to allow for ensemble storage

        """
        super(DynamicsEngineStorage, self)._init()

        self.init_variable('dynamicsengine_options', 'str', description="dynamicsengine_options[ensemble] is the json string of the options dict of engine 'ensemble'.")
        self.init_variable('dynamicsengine_type', 'str', description="dynamicsengine_type[ensemble] is the actual class name of engine 'ensemble'.")