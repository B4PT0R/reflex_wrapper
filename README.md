# reflex-wrapper

`reflex-wrapper` is a Python module that provides a wrapper on top of the reflex library to ease creating custom components as well as adding syntactic sugar to setup and interact with components after they are instantiated. It is meant to be "without loss", meaning that all that was possible to achieve with reflex is still possible using the wrapper, and as easily or more.

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
    def double_count(self):
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
    cnt2=Counter(count=cnt.double_count) # we can link a second counter's state to the first's, thus synchronizing their states.
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