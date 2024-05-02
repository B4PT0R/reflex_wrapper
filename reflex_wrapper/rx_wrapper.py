"""
Module used as a wrapper around the reflex library to ease custom components creation.
Defines a generic Component class that automates State init boilerplate and provides a more user-friendly interface to interact with components
"""

import reflex
from functools import wraps
from copy import copy

def get_class_dict(cls,excluded=()):
    """
    Returns a dict representing a given class, excluding chosen attributes
    """
    class_dict = {
        '__name__': cls.__name__,
        '__bases__': tuple(base for base in cls.__bases__ if base != object),
        '__metaclass__': type(cls),
        '__annotations__':{k:v for k,v in cls.__annotations__.items() if not k in excluded}
    }

    excluded_attributes = {'__dict__', '__weakref__', '__module__', '__qualname__','__annotations__',*excluded}
    class_dict.update({k:v for k,v in cls.__dict__.items() if k not in excluded_attributes})
    return class_dict

def build_class(class_dict):
    """
    Reconstructs a class from a class_dict
    """
    class_dict=copy(class_dict)
    name = class_dict.pop('__name__')
    bases = class_dict.pop('__bases__')
    metaclass = class_dict.pop('__metaclass__')
    attributes=dict(**class_dict)
    return metaclass(name, bases, attributes)

def auto_render(obj):
    """
    Makes sure obj is or returns a reflex.Component instance
    """
    if callable(obj):
        @wraps(obj)
        def decorated(*args,**kwargs)->reflex.Component:
            component=obj(*args,**kwargs)
            if isinstance(component,Component):
                return component._render()
            elif isinstance(component,reflex.Component):
                return component
            else:
                raise TypeError(f"{obj.__name__} must return a component object")
        return decorated
    else:
        if isinstance(obj,Component):
            return obj._render()
        elif isinstance(obj,reflex.Component):
            return obj
        else:
            raise TypeError(f"{obj} should be a component object")

class Component:

    _excluded=(
        '_excluded',
        '_state_model',
        '_state_attrs',
        '_constructor',
        '_create',
        '_setup_state_class',
        '_get_instance_state_class',
        'get_component',
        '_set_default',
        '_set_defaults_from_props',
        '_initialize',
        '__init__',
        '__getattr__',
        '__setattr__',
        '_render',
        '_is_state_attr',
        '_is_state_variable',
        '_is_state_setter',
        '__doc__'
    )
    
    _state_model=None
    _state_attrs=None
    _constructor=None
    
    @classmethod
    def _setup_state_model(cls):
        """
        Extract user defined attributes and methods from the Component subclass to construct the Pydantic state model (reflex.Base)
        """
        details=get_class_dict(cls,excluded=cls._excluded)
        name=details['__name__']
        cls._state_attrs=[k for k in details if k not in ('__name__','__bases__','__metaclass__','__annotations__')]
        details.update(__name__=name+'State',__bases__=(reflex.Base,),_instance_count=0)
        cls._state_model=build_class(details)
        # Remove state attrs from the component object to avoid messing with __getattr__
        for attr in cls._state_attrs:
            delattr(cls,attr)
   
    @classmethod 
    def _get_instance_state_class(cls):
        """
        Copy the state model into a reflex.State subclass, unique for each component instance.
        """
        if cls._state_model is None:
            cls._setup_state_model()
        cls._state_model._instance_count += 1
        instance_state_cls_name = f"{cls._state_model.__name__}_n{cls._state_model._instance_count}"
        instance_state_class = type(instance_state_cls_name, (cls._state_model, reflex.State), {})
        return instance_state_class
    
    def _is_state_attr(self,attr):
        """
        Checks whether an attr is a state attr
        """
        if self.state is None:
            return False
        else:
            return attr in self.__class__._state_attrs
        
    def _is_state_variable(self,attr):
        """
        Checks whether an attr is a state variable
        """
        return self._is_state_attr(attr) and attr in self.state.__fields__
    
    def _is_state_setter(self,attr):
        """
        Checks whether an attr is a state variable setter
        """
        return attr.startswith('set_') and self._is_state_variable(attr[4:])
    
    def _set_default(self,key,value):
        """
        Sets the default value of a state variable
        """
        self.state.__fields__[key].default=value

    def _set_defaults_from_props(self,props):
        """
        Sets defaults for state variables from props passed to the component
        Skip if the prop already refers to another state variable (possibly from another component) 
        """
        for key in list(props.keys()):
            if self._is_state_variable(key):
                value=props.pop(key)
                if not isinstance(value,reflex.Var):
                    self._set_default(key,value)
        return props
    
    def get_component(self,*childen,**props):
        """
        This method should be overriden when defining a custom component class
        """
        raise NotImplementedError("Custom components must implement a get_component method.")

    def _create(self,*children,**props):
        """
        Returns the corresponding reflex.Component instance and attach the state to it
        """
        props=self._set_defaults_from_props(props)
        component=auto_render(self.get_component)(*children,**props)
        component.State=self.state
        return component
    
    def _initialize(self):
        """
        Initializes the reflex.Component constructor:
        If none is specified at class level, this is a custom component so we initialize its state and constructor accordingly
        If one is already specified at class level, this is a default component, so we use its constructor directly.
        """
        if self.__class__._constructor is None:
            self.state=self.__class__._get_instance_state_class()
            self.constructor=self._create
        else:
            self.constructor=self.__class__._constructor

    def __init__(self,*children,**props):
        self.parent=None
        self.component=None
        self.state=None
        self.constructor=None
        self._initialize()
        self.props = dict(**props)
        children=self.props.get('children') or children
        for child in children:
            if isinstance(child,Component):
                child.parent=self
        self.props['children']=children

    def __getattr__(self,key):
        """
        Delegate attribute access to state / props
        Any state variable (reflex.Var) passed as state prop takes precedence over local state variables.
        """
        if self._is_state_variable(key):
            if key in self.props:
                value=self.props[key]
                if isinstance(value,reflex.Var):
                    return value
                else:
                    return getattr(self.state,key)
            else:
                return getattr(self.state,key)
        elif self._is_state_setter(key) or self._is_state_attr(key):
            return getattr(self.state,key)
        elif key in self.props:
            return self.props[key]
        else:
            raise AttributeError(f"Invalid attribute key: '{key}'")
        
    def __setattr__(self,key,value):
        """
        Delegate attribute setting to state / props
        """
        if key in ['parent','constructor','component','state','props']:
            super().__setattr__(key,value)
        elif self._is_state_variable(key):
            if not isinstance(value,reflex.Var):
                self._set_default(key,value)
            self.props[key]=value
        elif self._is_state_setter(key) or self._is_state_attr(key):
            raise AttributeError("Cannot override a state method.")
        else:
            self.props[key]=value

    def _render(self):
        """
        Renders the component
        ie. returns the corresponding reflex.Component instance
        """

        # First render the children
        rendered_children=[]
        for child in self.props['children']:
            if isinstance(child,Component):
                child=child._render()
            rendered_children.append(child)

        # Then render the props
        props={}
        for key,prop in self.props.items():
            if not key=='children':
                if isinstance(prop,Component):
                    prop=prop._render()
                props[key]=prop
        
        # Render the component by calling the constructor
        self.component=self.constructor(*rendered_children,**props)
        return self.component


def get_builtin_component(name=None,constructor=None):
    """
    Prepares a component class from a given builtin reflex constructor
    """
    return type(name,(Component,),dict(_constructor=constructor))

class App(reflex.App):

    """
    Overrides the reflex.App object to support Component objects as pages
    """

    def __init__(self,*args,**kwargs):
        reflex.App.__init__(self,*args,**kwargs)

    def add_page(self,component,*args,**kwargs):
        super().add_page(auto_render(component),*args,**kwargs)


class rx_submodule:
    
    _dict = {}

    def __init__(self, submodule_name):
        self.submodule_name = submodule_name
        try:
            self.module = getattr(reflex, submodule_name)
        except AttributeError:
            raise ImportError(f"The submodule {submodule_name} could not be found in the reflex library.")

    def __getattr__(self, key):
        full_key = f"{self.submodule_name.capitalize()}{key.capitalize()}"
        if full_key in rx_submodule._dict:
            return rx_submodule._dict[full_key]
        else:
            try:
                attr = getattr(self.module, key)
                new_cls = get_builtin_component(name=full_key, constructor=attr)
                rx_submodule._dict[full_key] = new_cls
                return new_cls
            except AttributeError:
                raise AttributeError(f"No component named {key} in the {self.submodule_name} submodule.")


class rx_meta(type):

    """
    Meta class to override __getattr__ in the RX class
    Does the routing to the appropriate object
    """

    def __getattr__(cls, key):
        if key in cls._reserved:
            return getattr(reflex,key)
        elif key in cls._submodules:
            return rx_submodule(key)
        elif key in globals():
            return globals()[key]
        elif key in cls._dict:
            return cls._dict[key]
        elif hasattr(reflex,key):
            new_cls=get_builtin_component(name=key.capitalize(),constructor=getattr(reflex,key))
            cls._dict[key]=new_cls
            return new_cls
        else:
            raise AttributeError(f"No reflex component named {key}.")

class rx(metaclass=rx_meta):
    """
    Class used as a replacement of the reflex module, supporting Components objects
    """
    _reserved=['page','var','cached_var','Base','State','theme','theme_panel','Var']
    _submodules=['chakra']
    _dict=dict()



        
    




