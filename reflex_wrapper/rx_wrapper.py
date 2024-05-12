"""
Module used as a wrapper around the reflex library to ease custom components creation.
Defines a generic Component class that automates State init boilerplate and provides a more user-friendly interface to interact with components
"""

import reflex
from functools import wraps
from types import FunctionType, CodeType
from copy import copy
from textwrap import dedent 
import uuid

def get_function(code_str, func_name):
    """ Compiles a function from a code string. Returns the corresponding function object."""
    code_str = dedent(code_str)
    compiled_code = compile(code_str, "<string>", "exec")
    func_code = next(obj for obj in compiled_code.co_consts if isinstance(obj, CodeType))
    return FunctionType(func_code, globals(), func_name)


def get_class_dict(cls,excluded=()):
    """
    Returns a dict representing a given class, excluding chosen attributes
    """
    excluded_attributes = {'__dict__', '__weakref__', '__module__', '__qualname__','__annotations__',*excluded}
    class_dict = {
        '__name__': cls.__name__,
        '__bases__': tuple(base for base in cls.__bases__ if base != object),
        '__annotations__':{k:v for k,v in cls.__annotations__.items() if not k in excluded},
        **{k:v for k,v in cls.__dict__.items() if k not in excluded_attributes}
    }
    return class_dict

def build_class(class_dict):
    """
    Reconstructs a class from a class_dict
    """
    class_dict=copy(class_dict)
    name = class_dict.pop('__name__')
    bases = class_dict.pop('__bases__')
    return type(name, bases, class_dict)

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


class State:

    _private=(
        '_private',
        '_state_model',
        '_state_attrs',
        '_setup_state_class',
        '_get_instance_state_class',
        '_state',
        '_set_default',
        '__init__',
        '__getattribute__',
        '__setattr__',
        '_is_state_attr',
        '_is_user_state_attr',
        '_is_state_variable',
        '_is_state_setter',
        '__doc__',
        '__class__'
    )

    _state_model=None
    _state_attrs=None
    
    @classmethod
    def _setup_state_model(cls):
        """
        Extract user defined attributes and methods from the State subclass to construct the Pydantic state model (reflex.Base)
        """
        details=get_class_dict(cls,excluded=cls._private)
        name=details['__name__']
        cls._state_attrs={k:v for k,v in details.items() if not k in ('__name__','__bases__','__annotations__')}
        details.update(__name__=name+'Model',__bases__=(reflex.Base,),_instance_count=0,_state_name=name)
        cls._state_model=build_class(details)
        for attr in cls._state_attrs:
            delattr(cls,attr)
   
    @classmethod 
    def _get_instance_state_class(cls):
        """
        Copy the state model into a reflex.State subclass, unique for each State instance.
        """
        if cls._state_model is None:
            cls._setup_state_model()
        cls._state_model._instance_count += 1
        instance_state_cls_name = f"{cls._state_model._state_name}_n{cls._state_model._instance_count}"
        instance_state_class = type(instance_state_cls_name, (cls._state_model, reflex.State),{})
        return instance_state_class
    
    def _is_user_state_attr(self,attr):
        """
        Checks whether an attr is a user-defined state attr
        """
        if not hasattr(self,'_state') or self._state is None:
            return False
        else:
            return attr in self.__class__._state_attrs
        
    def _is_state_variable(self,attr):
        """
        Checks whether an attr is a state variable
        """
        return self._is_user_state_attr(attr) and attr in self._state.__fields__
    
    def _is_state_setter(self,attr):
        """
        Checks whether an attr is a state setter
        """
        return attr.startswith('set_') and self._is_state_variable(attr[4:])
    
    def _is_state_attr(self,attr):
        """
        Checks whether an attr is a valid state attribute
        """
        return self._is_user_state_attr(attr) or self._is_state_setter(attr)
    
    def _set_default(self,key,value):
        """
        Sets the default value of a state variable
        """
        if self._is_state_variable(key):
            self._state.__fields__[key].default=value
        else:
            raise AttributeError(f"Could not assign state variable value. Invalid state variable: {key}")
    
    def __init__(self):
        self._state=self.__class__._get_instance_state_class()

    def __getattr__(self,key):
        """
        Delegate attribute access to the reflex.State object
        """    
        if self._is_state_attr(key):
            return getattr(self._state,key)
        else:
            raise AttributeError(f"Invalid state attribute: '{key}'")
        
    def __setattr__(self,key,value):
        """
        Delegate attribute setting to to the reflex.State object
        """
        if key in self.__class__._private:
            object.__setattr__(self,key,value)
        elif self._is_state_variable(key):
            self._set_default(key,value)
        elif self._is_state_attr(key):
            raise AttributeError(f"Cannot assign to a state attribute which is not a state variable: '{key}'.")
        else:
            raise AttributeError(f"Invalid state attribute: '{key}'")
        

class Component(State):

    _private=State._private+(
        '_init_constructor',
        '_constructor',
        '_attach_state',
        'props',
        'get_component',
        '_render'
    )

    _constructor=None
    
    def get_component(self,*childen,**props):
        """
        This method should be overriden when defining a custom component class
        """
        raise NotImplementedError("Custom components must implement a get_component method.")
    
    def _attach_state(self,func):
        """
        Decorator: takes a function returning a reflex.Component instance and attach the state to the returned component
        """
        @wraps(func)
        def decorated(*args,**kwargs):
            component=func(*args,**kwargs)
            component.State=self._state
            return component
        return decorated

    def _init_constructor(self):
        """
        The reflex.Component constructor:
        If none is specified at class level, this is a custom component so we return the decorated custom get_component method
        If one is already specified at class level, this is a default component, so we use its constructor directly.
        """
        if self.__class__._constructor is None:
            self._constructor=self._attach_state(auto_render(self.get_component))
        else:
            self._constructor=self.__class__._constructor

    def __init__(self,*children,**props):
        State.__init__(self)
        self._init_constructor()
        self.props = dict(**props)
        # the 'children' prop, if any, gets precedence over children passed as nested args (similar to React)
        children=self.props.get('children') or children
        self.props['children']=children

    def __getattr__(self,key):
        """
        Delegate attribute access to the reflex.State object
        """
        if self._is_state_attr(key):
            return getattr(self._state,key)
        elif key in self.props:
            return self.props[key]
        else:
            raise AttributeError(f"Invalid component attribute: '{key}'")
        
    def __setattr__(self,key,value):
        """
        Delegate attribute setting to to the reflex.State object or props
        """
        if key in self.__class__._private:
            object.__setattr__(self,key,value)
        elif self._is_state_variable(key):
            self._set_default(key,value)
            self.props[key]=value
        elif self._is_state_attr(key):
            raise AttributeError(f"Cannot assign to a component attribute which is not a prop or state variable: '{key}'.")
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
        return self._constructor(*rendered_children,**props)


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
    _reserved=['page','var','cached_var','Base','theme','theme_panel','Var','Config']
    _dict=dict()



        
    




