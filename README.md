# reflex-wrapper

`reflex-wrapper` is a Python module that provides a wrapper on top of the reflex library. It mostly behaves just like the reflex module, but simplifies the public API to make creating custom components more user-friendly. The idea behind this wrapper was that, in reflex, States are pydantic models (classes) who are only instantiated per-session by the server itself. This means that you never should instantiate state classes directly in your reflex code. As a matter of fact, what would be considered "instances" of a State in reflex are actualy subclasses of an initial pydantic rx.State class (but still classes!).
This design choice, while being very elegant on a technical point of view for input validation and multi-session state management, also made the objet model less intuitive to a regular python developper, who expects to create 3 independant stateful components by instantiating the component class three times and that's it. To work around this, I created a custom Component class that abstracts away these pydantic state shenanigans and allows to use reflex components as normal instances of their Component subclass. 

All standard reflex objects accessed from the rx wrapper should be automatically converted into these Components, or into objects supporting them, so that you don't have to bother about any additional overhead introduced by the wrapper and just focus on creating your app.

I'm rather new to Reflex, this small project is meant as an exercise and reflects my current (limited) understanding of the library. I may have neglected to cover some important functionalities. Feel free to check the source code and suggest improvements.

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
    cnt1=Counter(count=10,background='blue') # we can intialize the count state value directly from props
    cnt2=Counter()
    cnt2.count=5
    cnt2.background='green' # we can also edit via attribute style access after instantiation
    btn1=rx.button("Click to add 2 to the first counter",on_click=cnt1.set_count(cnt1.count+2)) # state variables / methods / setters can be accessed directly from the component instance
    cnt3=Counter(count=cnt1.twice_the_count) # we can enforce cnt3's count to echo some (computed) state var of cnt1. (methods modifying cnt3's count will have no visible effect anymore)
    lbl1=rx.text(cnt3.count) # will show cnt1.twice_the_count 
    box=rx.box(
        cnt1,
        cnt2,
        cnt3,
        lbl1,
        btn1
    )
    return box

app=rx.App()
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.