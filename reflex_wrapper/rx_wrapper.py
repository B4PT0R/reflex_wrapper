"""
Module used as a wrapper around the reflex library to ease custom components creation.
Defines a generic Component class that automates State init boilerplate and provides a more user-friendly interface to interact with components
"""

import reflex
from functools import wraps
from copy import copy
import uuid

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


def use_state(default,vartype=None):
    """
    Creates a state with a single var 'value' set to default and returns the corresponding state var and setter
    """
    vartype=vartype or type(default)
    attributes={
        'value':default,
        '__annotations__':{'value':vartype}
    }
    cls_name="State_"+str(uuid.uuid4())
    state=type(cls_name,(reflex.State,),attributes)
    state_var=state.value
    state_setter=state.set_value
    return state_var,state_setter

class StateWrapper:

    """
    Class acting as a reflex.State proxy, allowing to pass reflex (computed) vars as default values for other state variables.
    Meant to achieve staightforward state synchronization between components with a priori independent states.
    """

    def __init__(self,state):
        self.state=state
        self.dict=dict()

    def __getattr__(self,attr):
        if attr in self.dict:
            return self.dict[attr]
        else:
            return getattr(self.state,attr)
    
    def __setattr__(self,attr,value):
        if attr in ['state','dict']:
            super().__setattr__(attr,value)
        else:
            if isinstance(value,reflex.Var):
                self.dict[attr]=value
            else:
                setattr(self.state,attr,value)

    def __delattr__(self,attr):
        if attr in ['state','dict']:
            super().__delattr__(attr)
        else:
            if attr in self.dict:
                del self.dict[attr]
            else:
                delattr(self.state,attr)



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
        Checks whether an attr is a user-defined state attr
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
    
    def _is_state(self,attr):
        """
        Check whether an attr is a valid state attr
        """
        return self._is_state_attr(attr) or self._is_state_setter(attr)
    
    def _set_default(self,key,value):
        """
        Sets the default value of a state variable
        """
        self.state.__fields__[key].default=value

    def _set_defaults_from_props(self):
        """
        Sets defaults for state variables from props passed to the component
        Skip if the prop already refers to another state variable (possibly from another component) 
        """
        for key,value in self.props.items():
            if self._is_state_variable(key):
                if isinstance(value,(reflex.Var,reflex.vars.ComputedVar)):
                    setattr(self.state,key,value)
                else:
                    self._set_default(key,value)
                    
    def _get_reflex_props(self):
        """
        filters out state variables from props before passing them to the reflex constructor
        """
        return {k:v for k,v in self.props.items() if not self._is_state(k)}
    
    def get_component(self,*childen,**props):
        """
        This method should be overriden when defining a custom component class
        """
        raise NotImplementedError("Custom components must implement a get_component method.")

    def _create(self,*children,**props):
        """
        Returns the corresponding reflex.Component instance and attach the state to it
        """
        component=auto_render(self.get_component)(*children,**props)
        #component.State=self.state
        return component
    
    def _initialize(self):
        """
        Initializes the reflex.Component constructor:
        If none is specified at class level, this is a custom component so we initialize its state and constructor accordingly
        If one is already specified at class level, this is a default component, so we use its constructor directly.
        """
        if self.__class__._constructor is None:
            self.state=StateWrapper(self.__class__._get_instance_state_class())
            self.constructor=self._create
        else:
            self.constructor=self.__class__._constructor

    def __init__(self,*children,**props):
        self.parent=None
        self.state=None
        self.constructor=None
        self._initialize()
        self.props = dict(**props)
        # the 'children' prop, if any, gets precedence over children passed as nested args (similar to React)
        children=self.props.get('children') or children
        for child in children:
            if isinstance(child,Component):
                child.parent=self
        self.props['children']=children
        self._set_defaults_from_props()

    def __getattr__(self,key):
        """
        Delegate attribute access to state / props
        """
        if self._is_state(key):
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
            if not isinstance(value,(reflex.Var,reflex.vars.ComputedVar)):
                self._set_default(key,value)
            else:
                setattr(self.state,key,value)
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
        for key,prop in self._get_reflex_props().items():
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

def capitalize(string):
    if len(string)>0:
        return string[0].upper()+string[1:]
    else:
        return ""

def resolve_attr_chain(chain):
    obj=reflex
    path='reflex'
    for attr in chain:
        if hasattr(obj,attr):
            path+=f'.{attr}'
            obj=getattr(obj,attr)
        else:
            raise AttributeError(f"{path} has no attribute '{attr}'.")
    return obj

def chain_as_path(chain):
    return 'reflex.'+'.'.join(chain)

def chain_as_name(chain):
    return ''.join(capitalize(name) for name in chain)

class rx_submodule:

    """
    Class representing a reflex submodule, to implement attribute chain lookup from the rx class.
    Does the routing to the appropriate component/object/submodule
    """

    def __init__(self,chain):
        self.chain=chain
        self.path=chain_as_path(self.chain)
        self.obj=resolve_attr_chain(self.chain)

    def __getattr__(self, key):
        chain=self.chain+[key]
        path=chain_as_path(chain)
        if path in rx._dict:
            return rx._dict[path]
        elif hasattr(self.obj,key) and callable(getattr(self.obj,key)):
            name=chain_as_name(chain)
            new_cls=get_builtin_component(name=name,constructor=getattr(self.obj,key))
            rx._dict[path]=new_cls
            return new_cls
        elif hasattr(self.obj,key):
            return rx_submodule(chain)
        else:
            raise AttributeError(f"{self.path} has no attribute named {key}.")


class rx_meta(type):

    """
    Metaclass to override __getattr__ in the rx class
    Does the routing to the appropriate component/object/submodule
    """

    def __getattr__(cls, key):
        if key in cls._reserved:
            return getattr(reflex,key)
        elif key in globals():
            return globals()[key]
        
        chain=[key]
        path=chain_as_path(chain)

        if path in rx._dict:
            return rx._dict[path]
        elif hasattr(reflex,key) and callable(getattr(reflex,key)):
            name=chain_as_name(chain)
            new_cls=get_builtin_component(name=name,constructor=getattr(reflex,key))
            rx._dict[path]=new_cls
            return new_cls
        elif hasattr(reflex,key):
            return rx_submodule(chain)
        else:
            raise AttributeError(f"reflex has no attribute named {key}.")


class rx(metaclass=rx_meta):
    """
    Class used as a replacement of the reflex module, supporting Components objects
    (its __getattr__ is implemented by the metaclass defined above)
    """
    _reserved=['page','var','cached_var','Base','State','theme','theme_panel','Var','Config']
    _dict=dict()



        
    




