from django import core
from django.utils.functional import curry
from django.core.exceptions import ImproperlyConfigured
from django.db import connections, _default
from django.db.models.query import QuerySet
from django.dispatch import dispatcher
from django.db.models import signals, get_apps, get_models
from django.db.models.fields import FieldDoesNotExist
from django.utils.datastructures import SortedDict

try:
    # Only exists in Python 2.4+
    from threading import local
except ImportError:
    # Import copy of _thread_local.py from Python 2.4
    from django.utils._threading_local import local

# Size of each "chunk" for get_iterator calls.
# Larger values are slightly faster at the expense of more storage space.
GET_ITERATOR_CHUNK_SIZE = 100

def ensure_default_manager(sender):
    cls = sender
    if not hasattr(cls, '_default_manager'):
        # Create the default manager, if needed.
        try:
            cls._meta.get_field('objects')
            raise ValueError, "Model %s must specify a custom Manager, because it has a field named 'objects'" % cls.__name__
        except FieldDoesNotExist:
            pass
        cls.add_to_class('objects', Manager())
    elif cls._default_manager.model != cls:
        # cls is an inherited model; don't want the parent manager
        cls.add_to_class('objects', Manager())
dispatcher.connect(ensure_default_manager, signal=signals.class_prepared)

class ConnectionInfoDescriptor(object):
    """Descriptor used to access database connection information from a
    manager or other connection holder. Keeps a thread-local cache of
    connections per instance, and always returns the same connection for an
    instance in particular thread during a particular request.

    Any object that includes an attribute ``model`` that holds a model class
    can use this descriptor to manage connections.
    """
    
    def __init__(self):
        self.cnx = local()
        self.cnx.cache = {}
        
    def __get__(self, instance, type=None):
        if instance is None:
            raise AttributeError, \
                "ConnectionInfo is accessible only through an instance"
        instance_connection = self.cnx.cache.get(instance, None)
        if instance_connection is None:
            instance_connection = self.get_connection(instance)
            def reset():
                self.reset(instance)
            dispatcher.connect(reset, signal=core.signals.request_finished)
            self.cnx.cache[instance] = instance_connection
        return instance_connection

    def __set__(self, instance, value):
        self.cnx.cache[instance] = instance_connection

    def __delete__(self, instance):
        self.reset(instance)

    def get_connection(self, instance):
        from django.conf import settings
        app = instance.model._meta.app_label
        model = instance.model.__name__
        app_model = "%s.%s" % (app, model)

        # Quick exit if no OTHER_DATABASES defined
        if (not hasattr(settings, 'OTHER_DATABASES')
            or not settings.OTHER_DATABASES):
            return connections[_default]
        # Look in MODELS for the best match: app_label.Model. If that isn't
        # found, take just app_label. If nothing is found, use the default
        maybe = None
        for name, db_def in settings.OTHER_DATABASES.items():
            if not 'MODELS' in db_def:
                continue
            mods = db_def['MODELS']
            # Can't get a better match than this
            if app_model in mods:
                return connections[name]
            elif app in mods:
                if maybe is not None:
                    raise ImproperlyConfigured, \
                        "App %s appears in more than one OTHER_DATABASES " \
                        "setting (%s and %s)" % (maybe, name)
                maybe = name
        if maybe:
            return connections[name]
        # No named connection for this model; use the default
        return connections[_default]            
            
    def reset(self, instance):
        self.cnx.cache[instance] = None


class Manager(object):
    # Tracks each time a Manager instance is created. Used to retain order.
    creation_counter = 0
    db = ConnectionInfoDescriptor()
    
    def __init__(self):
        super(Manager, self).__init__()
        # Increase the creation counter, and save our local copy.
        self.creation_counter = Manager.creation_counter
        Manager.creation_counter += 1
        self.model = None

    def contribute_to_class(self, model, name):
        # TODO: Use weakref because of possible memory leak / circular reference.
        self.model = model
        setattr(model, name, ManagerDescriptor(self))
        if not hasattr(model, '_default_manager') \
            or self.creation_counter < model._default_manager.creation_counter \
            or model._default_manager.model != model:
            model._default_manager = self
        
    #######################
    # PROXIES TO QUERYSET #
    #######################

    def get_query_set(self):
        """Returns a new QuerySet object.  Subclasses can override this method
        to easily customise the behaviour of the Manager.
        """
        return QuerySet(self.model)

    def all(self):
        return self.get_query_set()

    def count(self):
        return self.get_query_set().count()

    def dates(self, *args, **kwargs):
        return self.get_query_set().dates(*args, **kwargs)

    def distinct(self, *args, **kwargs):
        return self.get_query_set().distinct(*args, **kwargs)

    def extra(self, *args, **kwargs):
        return self.get_query_set().extra(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.get_query_set().get(*args, **kwargs)

    def get_or_create(self, **kwargs):
        return self.get_query_set().get_or_create(**kwargs)
        
    def create(self, **kwargs):
        return self.get_query_set().create(**kwargs)

    def filter(self, *args, **kwargs):
        return self.get_query_set().filter(*args, **kwargs)

    def complex_filter(self, *args, **kwargs):
        return self.get_query_set().complex_filter(*args, **kwargs)

    def exclude(self, *args, **kwargs):
        return self.get_query_set().exclude(*args, **kwargs)

    def in_bulk(self, *args, **kwargs):
        return self.get_query_set().in_bulk(*args, **kwargs)

    def iterator(self, *args, **kwargs):
        return self.get_query_set().iterator(*args, **kwargs)

    def latest(self, *args, **kwargs):
        return self.get_query_set().latest(*args, **kwargs)

    def order_by(self, *args, **kwargs):
        return self.get_query_set().order_by(*args, **kwargs)

    def select_related(self, *args, **kwargs):
        return self.get_query_set().select_related(*args, **kwargs)

    def values(self, *args, **kwargs):
        return self.get_query_set().values(*args, **kwargs)

    #######################
    # SCHEMA MANIPULATION #
    #######################

    def install(self, initial_data=False):
        """Install my model's table, indexes and (if requested) initial data.

        Returns a dict of pending statements, keyed by the model that
        needs to be created before the statements can be executed.
        (Pending statements are those that could not yet be executed,
        such as foreign key constraints for tables that don't exist at
        install time.)
        """
        builder = self.db.get_creation_module().builder
        run, pending = builder.get_create_table(self.model)
        run += builder.get_create_indexes(self.model)
        if initial_data:
            run += builder.get_initialdata(self.model)
        many_many = builder.get_create_many_to_many(self.model)

        for statement in run:
            statement.execute()
        for klass, statements in many_many.items():
            if klass in builder.models_already_seen:
                for statement in statements:
                    statement.execute()
            else:
                pending.setdefault(klass, []).extend(statements)
        return pending

    def load_initial_data(self):
        """Load initial data for my model into the database."""
        pass # FIXME

    def drop(self):
        """Drop my model's table."""
        pass # FIXME

    def get_installed_models(self, table_list):
        """Get list of models installed, given a list of tables
        """
        all_models = []
        for app in get_apps():
            for model in get_models(app):
                all_models.append(model)
                return set([m for m in all_models
                            if m._meta.db_table in table_list])

    def get_table_list(self):
        """Get list of tables accessible via my model's connection.
        """
        builder = self.db.get_creation_module().builder
        return builder.get_table_list(self.db)
    
class ManagerDescriptor(object):
    # This class ensures managers aren't accessible via model instances.
    # For example, Poll.objects works, but poll_obj.objects raises AttributeError.
    def __init__(self, manager):
        self.manager = manager

    def __get__(self, instance, type=None):
        if instance != None:
            raise AttributeError, "Manager isn't accessible via %s instances" % type.__name__
        return self.manager

