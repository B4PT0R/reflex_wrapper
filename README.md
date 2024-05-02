# reflex-wrapper

`reflex-wrapper` is a Python module that provides a wrapper on top of the reflex library. It mostly behaves just like the reflex module, but simplifies the public API to make creating custom components more user-friendly. The idea behind this wrapper was that, in reflex, States are pydantic models (classes) who are only instantiated per-session by the server itself. This means that you never should instantiate a state classes directly in your reflex code. As a matter of fact, what would be considered "instances" of a State in reflex are actualy subclasses of an initial pydantic rx.State class (but still classes!).
This design choice, while being very elegant on a technical point of view for input validation and multi-session state management, also made the objet model less intuitive to a regular python developper, who expects to create 3 independant stateful components by instantiating the component class three times and that's it. To work around this, I created a custom Component class that abstracts away these pydantic state shenanigans and allows to use reflex components as normal instances of their Component subclass. 

All standard reflex components are also automatically converted into Component objects so that you don't have to think about it and just focus on creating your app.

## Installation

```bash
pip install reflex-wrapper
```

## Usage

```python
from reflex_wrapper import rx

# Define a custom component by subclassing the rx.Component class

class Counter(rx.Component):

    count: int = 0

    @rx.var
    def twice_the_count(self):
        return 2*self.count

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1

    # Above is the state definition with a state var, a computed var and event handlers
    #----------------------------------------------------------------------
    # Below is the get_component method that returns the state-dependant layout of the component

    def get_component(self,*children, **props):
        return rx.hstack(
            rx.button("Decrement", on_click=self.decrement),
            rx.text(self.count),
            rx.button("Increment", on_click=self.increment),
            **props,
        )

# Notice that get_component is not defined as a class method but a regular instance method
# Notice also that state variables and event handlers can be accessed directly from self

# Now we can reuse this component to create a page layout
# No need to define counter=Counter.create, the Counter class can be instantiated directly into Component objects

@rx.page() # Decorators still work
def index():
    cnt=Counter(count=10,background='blue') # we can intialize the count state value directly from props
    cnt.count=5
    cnt.background='green' # we can also edit via attribute style access after instantiation
    btn1=rx.button("Click to add 2",on_click=cnt.set_count(cnt.count+2)) # we can use state setters like this
    cnt2=Counter(count=cnt.twice_the_count) # we can link a second counter's state to some state var of the first, thus synchronizing the second counter. 
    box=rx.box(
        cnt,
        cnt2
        btn1,
    )
    return box

app=rx.App()
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.