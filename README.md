# pyken

WIP: FFI into Aiken blueprints from Python with ease.

## Example

Here is our fancy `hello.ak` example in Aiken which we want to call from Python:

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

# This script assumes execution from the Aiken project directory.
# You can also provide the path to that directory as a parameter.
blueprint = Blueprint("hello", "greet")

# `blueprint` object serves two purposes:
# 1. It is an FFI to a UPLC function exposed through Aiken blueprint.
# 2. It is a namespace which contains all the types (with constructors)
#    defined in the blueprint and needed to call the function.
entity = blueprint.hello.Entity.Person("paluh")

response = blueprint(entity)

# Result contains the regular pieces from `aiken uplc eval` output.
assert response.result == "Hello, paluh!"
assert response.mem > 0
assert response.cpu > 0

# Some non-parametric constructors are exposed as values directly.
mercury = blueprint.hello.Planet.Mercury
planet = blueprint.hello.Entity.Planet(mercury)

response = blueprint(planet)
assert response.result == "Hello, Mercury!"
```

Minor comment about the example above: it is not a good idea to accept/work with
strings in Aiken/Plutus. Under the hood it requires a decoding pass between
bytes and string.

## Usage

This package depends on `aiken` being available in your PATH.

## Credits

This is rather trivial script. It is built on top of the excellent `opshin/uplc`
library and Aiken.
