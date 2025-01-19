# pyken

WIP: FFI into Aiken bluprints from Python with ease.

## Example

Here is our fancy `hello.ak` world example in Aiken which we want to call from
Python:

```aiken
use aiken/builtin.{append_string}

pub type Planet {
  Mercury
  Venus
  Earth
  Mars
  Jupiter
  Saturn
  Uranus
}

pub type Entity {
  Person {
    name: String,
  }
  Planet(Planet)
}

pub fn greet(entity: Entity) -> String {
  when entity is {
    Person { name } -> {
      append_string(append_string(@"Hello, ", name), @"!")
    }
    Planet(planet) -> {
      when planet is {
        Mercury -> @"Hello, Mercury!"
        Venus -> @"Hello, Venus!"
        Earth -> @"Hello, Earth!"
        Mars -> @"Hello, Mars!"
        Jupiter -> @"Hello, Jupiter!"
        Saturn -> @"Hello, Saturn!"
        Uranus -> @"Hello, Uranus!"
      }
    }
  }
}
```

Let's call that function from Python:

```python
from pyken import Blueprint

blueprint = Blueprint("hello", "greet")

# `blueprint` objects serves two purposes:
# 1. It is a function which FFI into a UPLC function
#    exposed through Aiken blueprint.
# 2. It is a namespace which contains all the types
#    defined in the blueprint and needed to call the function.
entity = blueprint.hello.Entity.Person("paluh")

response = blueprint(entity)

# Result contains the regular pieces from `aiken uplc eval` output.
assert response.result == "Hello, paluh!"

# Some non parametric constructors are exposed as values directly.
mercury = blueprint.hello.Planet.Mercury
planet = blueprint.hello.Entity.Planet(mercury)

# Even more values
assert blueprint(planet).result == "Hello, Mercury!"
```

Minor comment about the example above: it is not good idea to accept/work with
strings in Aiken/Plutus. Under the hood it requires a decoding pass between
bytes and string.

## Usage

This package depends on `aiken` being available in your PATH and currently can
be called only from the project directory.

## Credits

This is rather trivial script but it is build on top of great `opshin/uplc` lib
and the Aiken itself of course.
