from pyken import Blueprint
from pathlib import Path

# We need to pass current directory to the Blueprint constructor as absolute path
project_directory = Path(__file__).parent
blueprint = Blueprint("hello", "greet", aiken_project_directory=project_directory)

# `blueprint` objects serves two purposes:
# 1. It is a function which FFI into a UPLC function
#    exposed through Aiken blueprint.
# 2. It is a namespace which contains all the types
#    defined in the blueprint and needed to call the function.
entity = blueprint.hello.Entity.Person("paluh")

response = blueprint(entity)

# Result contains the regular pieces from `aiken uplc eval` output.
assert response.result == "Hello, paluh!", f"Expected greeting from paluh but got {response.result}"

# Some non parametric constructors are exposed as values directly.
mercury = blueprint.hello.Planet.Mercury
planet = blueprint.hello.Entity.Planet(mercury)


response = blueprint(planet)
assert response.result == "Hello, Mercury!", f"Expected greeting from Mercury but got '{response.result}'"

# The response contains also mem and cpu usage.
assert response.mem > 0, f"Expected non-zero memory usage but got {response.mem}"
assert response.cpu > 0, f"Expected non-zero CPU usage but got {response.cpu}"
