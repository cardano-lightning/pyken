import json
from collections import namedtuple
from dataclasses import make_dataclass
from typing import Any
import uplc.ast
import uplc.tools
import subprocess
import sys

def run_command(cmd, debug=True):
    log = print
    if not debug:
        log = lambda x: None
    log(f"$ {cmd}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    # fail fast
    if result.returncode != 0:
        log(f"Command failed: {result.returncode}")
        log(f"Command failed: {result.stderr}")
        sys.exit(1)
    return result.stdout

# Non parametric "well-known" types:
AikenSimpleType = namedtuple('AikenSimpleType', ['name'])
AikenBoolType = AikenSimpleType("Bool")
AikenByteArrayType = AikenSimpleType("ByteArray")
AikenDataType = AikenSimpleType("Data")
AikenIntType = AikenSimpleType("Integer")
AikenStringType = AikenSimpleType("String")

# Parametric "well-known" types:
class AikenListType(namedtuple('AikenListType', ['name', 'a'])):
    __slots__ = ()
    def __new__(cls, t_ref):
        name = f"List<{t_ref}>"
        return super(AikenListType, cls).__new__(cls, name, t_ref)
class AikenPairType(namedtuple('AikenPairType', ['name', 'fst', 'snd'])):
    __slots__ = ()
    def __new__(cls, fst, snd):
        name = f"Pair<{fst.name}, {snd.name}>"
        return super(AikenPairType, cls).__new__(cls, name, fst, snd)
class AikenTupleType(namedtuple('AikenTupleType', ['name', 'fields'])):
    __slots__ = ()
    def __new__(cls, fields):
        name = f"Tuple<{', '.join(t_ref for t_ref in fields)}>"
        return super(AikenTupleType, cls).__new__(cls, name, fields)

# User defined types:
AikenFieldType = namedtuple('AikenFieldType', ['name', 'type'])
AikenEnumConstructorType = namedtuple('AikenEnumConstructorType', ['name', 'index', 'fields'])
AikenEnumType = namedtuple('AikenEnumType', ['name', 'constructors'])

## For most types beside `Enum` can map Python to Aiken types directly.
AikenEnumValue = namedtuple('AikenEnumValue', ['index', 'fields'])
AikenPairValue = namedtuple('AikenPairValue', ['fst', 'snd'])

class AikenTerm(namedtuple('AikenTerm', ['value', 'type', 'type_refs'])):
    @staticmethod
    def from_typed_value(python_value, aiken_type, type_refs):
        if aiken_type == AikenBoolType:
            assert type(python_value) == bool, f"Expecting a boolean value: {python_value}"
            return AikenTerm(python_value, aiken_type, type_refs)
        elif aiken_type == AikenByteArrayType:
            assert type(python_value) == bytes, f"Expecting a bytes value: {python_value}"
            return AikenTerm(python_value, aiken_type, type_refs)
        elif aiken_type == AikenIntType:
            assert type(python_value) == int, f"Expecting an integer value: {python_value}"
            return AikenTerm(python_value, aiken_type, type_refs)
        elif aiken_type == AikenStringType:
            assert type(python_value) == str, f"Expecting a string value: {python_value}"
            return AikenTerm(python_value, aiken_type, type_refs)
        elif isinstance(aiken_type, AikenListType):
            assert type(python_value) == list, f"Expecting a list value: {python_value}"
            elems = [ AikenTerm.from_typed_value(v, type_refs[aiken_type.a], type_refs) for v in python_value ]
            return AikenTerm(elems, aiken_type, type_refs)
        elif isinstance(aiken_type, AikenTupleType):
            assert type(python_value) == tuple, f"Expecting a tuple value: {python_value}"
            assert len(python_value) == len(aiken_type.fields), f"Expecting a tuple with {len(aiken_type.fields)} elements: {python_value}"
            fields = [AikenTerm.from_typed_value(v, type_refs[t], type_refs) for v, t in zip(python_value, aiken_type.fields)]
            return AikenTerm(fields, aiken_type, type_refs)
        elif isinstance(aiken_type, AikenPairType):
            assert isinstance(python_value, tuple), f"Expecting a pair value: {python_value}"
            assert len(python_value) == 2, f"Expecting a pair with 2 elements: {python_value}"
            fst = AikenTerm.from_typed_value(python_value.fst, type_refs[aiken_type.fst], type_refs)
            snd = AikenTerm.from_typed_value(python_value.snd, type_refs[aiken_type.snd], type_refs)
            return AikenTerm(AikenPairValue(fst, snd), aiken_type, type_refs)
        elif isinstance(aiken_type, AikenEnumType):
            assert isinstance(python_value, AikenEnumValue), f"Expecting an enum value: {python_value}, {python_value.__class__}"
            print(python_value)
            print(python_value.fields)
            constructor_type = aiken_type.constructors[python_value.index]
            fields = [AikenTerm.from_typed_value(v, type_refs[t_ref], type_refs) for v, t_ref in zip(python_value.fields, constructor_type.fields)]
            return AikenTerm(AikenEnumValue(python_value.index, fields), aiken_type, type_refs)
        raise ValueError(f"Unknown type: {aiken_type}")

    def to_uplc(self):
        if self.type == AikenBoolType:
            index = (1 if self.value else 0)
            return uplc.ast.PlutusConstr(index, [])
        elif self.type == AikenByteArrayType:
            return uplc.ast.PlutusByteString(self.value)
        elif self.type == AikenIntType:
            return uplc.ast.PlutusInteger(self.value)
        elif self.type == AikenStringType:
            # If string is accepted as an argument Aiken accepts really a bytestring and decodes it.
            # There is no Data constructor which can handle String.
            bytes = self.value.encode('utf-8')
            return uplc.ast.PlutusByteString(bytes)
        elif isinstance(self.type, AikenListType):
            elems = [t.to_uplc() for t in self.value]
            return uplc.ast.PlutusList(elems)
        elif isinstance(self.type, AikenTupleType):
            fields = [t.to_uplc() for t in self.value]
            return uplc.ast.PlutusList(fields)
        elif isinstance(self.type, AikenPairType):
            fst = self.value.fst.to_uplc()
            snd = self.value.snd.to_uplc()
            return uplc.ast.PlutusList([fst, snd])
        elif isinstance(self.type, AikenEnumType):
            fields = [t.to_uplc() for t in self.value.fields]
            return uplc.ast.PlutusConstr(self.value.index, fields)
        raise ValueError(f"Unknown type: {self.type}")

    def __repr__(self):
        return f"AikenTerm({self.value} :: {self.type})"

# This pass creates types with references
TypeReference = namedtuple('TypeReference', ['name'])
def parse_type_reference(reference_str, valid_refs):
    if not reference_str.startswith("#/definitions/"):
        raise ValueError(f"Unknown reference: {reference_str}")
    def_reference = reference_str[len("#/definitions/"):].replace("~1", "/")
    if def_reference not in valid_refs:
        raise ValueError(f"Unknown reference: {reference_str}, {ref}")
    return def_reference

def parse_constructor(constructor, index, valid_refs):
    title = constructor['title']
    fields = [parse_type_reference(field['$ref'], valid_refs) for field in constructor['fields']]
    return AikenEnumConstructorType(title, index, fields)

def parse_definition(ref, definition, valid_refs):
    # It seems that we have mandatory `title` and the other pieces allow us to 
    # distinguish between different types of definitions.
    title = definition.get('title', ref)
    if 'dataType' in definition:
        if definition['dataType'] == 'integer':
            return AikenIntType
        elif definition['dataType'] == 'bytes':
            return AikenByteArrayType
        elif definition['dataType'] == 'list':
            # Now it is funny part - if a list contains only a single item element then it is really a list type.
            # Otherwise it is a tuple type.
            if len(definition['items']) == 1:
                ref_str = definition['items']['$ref']
                return AikenListType(parse_type_reference(ref_str, valid_refs))
            else:
                references = [parse_type_reference(item['$ref'], valid_refs) for item in definition['items']]
                return AikenTupleType(references)
        elif definition['dataType'] == '#string':
            return AikenStringType
    elif 'anyOf' in definition:
        if (definition['title'] == 'Bool'
            and [c['title'] for c in definition['anyOf']] == ['False', 'True']
            and [len(c['fields']) for c in definition['anyOf']] == [0, 0]):
            return AikenBoolType
        constructors = [parse_constructor(constructor, index, valid_refs) for index, constructor in enumerate(definition['anyOf'])]
        return AikenEnumType(title, constructors)
    raise ValueError(f"Unknown definition: {definition}")

### Given the above set of helpers we want to parse definitions sections from a JSON like that:
test_blueprint = (
    {
      "name": "cheque.accept_cheques",
      "parameters": [
        {
          "title": "cheques",
          "schema": {
            "$ref": "#/definitions/List$cheque~1Cheque"
          }
        }
      ],
      "compiledCode": "5837010100323232253330023370e664600200244a66600a00229000099b8048008cc008008c018004dd6000a40002940528ab9a5573eae881",
      "hash": "9f7a498b186048b088d21bb6b1b7875e67fe7939ab7cdcb26a95acea",
      "definitions": {
        "Amount": {
          "title": "Amount",
          "dataType": "integer"
        },
        "Bytes32": {
          "title": "Bytes32",
          "dataType": "bytes"
        },
        "Htlc": {
          "title": "Htlc",
          "dataType": "list",
          "items": [
            {
              "$ref": "#/definitions/Index"
            },
            {
              "$ref": "#/definitions/Amount"
            },
            {
              "$ref": "#/definitions/Timeout"
            },
            {
              "$ref": "#/definitions/cheque~1HashLock"
            }
          ]
        },
        "Index": {
          "title": "Index",
          "dataType": "integer"
        },
        "List$cheque/Cheque": {
          "dataType": "list",
          "items": {
            "$ref": "#/definitions/cheque~1Cheque"
          }
        },
        "Normal": {
          "title": "Normal",
          "dataType": "list",
          "items": [
            {
              "$ref": "#/definitions/Index"
            },
            {
              "$ref": "#/definitions/Amount"
            }
          ]
        },
        "Timeout": {
          "title": "Timeout",
          "dataType": "integer"
        },
        "cheque/Cheque": {
          "title": "Cheque",
          "anyOf": [
            {
              "title": "NormalCheque",
              "dataType": "constructor",
              "index": 0,
              "fields": [
                {
                  "$ref": "#/definitions/Normal"
                }
              ]
            },
            {
              "title": "HtlcCheque",
              "dataType": "constructor",
              "index": 1,
              "fields": [
                {
                  "$ref": "#/definitions/Htlc"
                }
              ]
            }
          ]
        },
        "cheque/HashLock": {
          "title": "HashLock",
          "anyOf": [
            {
              "title": "Blake2b256Lock",
              "dataType": "constructor",
              "index": 0,
              "fields": [
                {
                  "$ref": "#/definitions/Bytes32"
                }
              ]
            },
            {
              "title": "Sha2256Lock",
              "dataType": "constructor",
              "index": 1,
              "fields": [
                {
                  "$ref": "#/definitions/Bytes32"
                }
              ]
            },
            {
              "title": "Sha3256Lock",
              "dataType": "constructor",
              "index": 2,
              "fields": [
                {
                  "$ref": "#/definitions/Bytes32"
                }
              ]
            }
          ]
        }
      }
    }
)

class BlueprintJSON(namedtuple('BlueprintJSON', ['name', 'parameters', 'definitions', 'compiled_code', 'hash'])):
    __slots__ = ()

    def __new__(cls, module_name, function_name, aiken_project_directory=None):
        project_directory = f"{aiken_project_directory}" if aiken_project_directory else ""
        blueprint_json = json.loads(run_command(f"aiken export --module {module_name} --name {function_name} {project_directory}"))
        return cls.from_json(blueprint_json)

    @staticmethod
    def _parse_parameter(parameter_json, type_refs):
        name = parameter_json['title']
        ref_str = parameter_json['schema']['$ref']
        type_ref = parse_type_reference(ref_str, type_refs)
        return name, type_ref

    @classmethod
    def from_json(cls, blueprint_json):
        definitions = blueprint_json['definitions']
        type_refs = set(definitions.keys())
        name = blueprint_json['name']
        parameters = [BlueprintJSON._parse_parameter(parameter, type_refs) for parameter in blueprint_json['parameters']]
        type_refs = {ref: parse_definition(ref, definition, type_refs) for ref, definition in definitions.items()}
        compiled_code = blueprint_json['compiledCode']
        hash = blueprint_json['hash']
        return super(BlueprintJSON, cls).__new__(cls, name, parameters, type_refs, compiled_code, hash)


# Let's try to parse:
blueprint = BlueprintJSON.from_json(test_blueprint)

for (n, d) in blueprint.definitions.items():
    print(f"{n} = {d.name}")

class Identifier(namedtuple('Identifier', ['ref', 'name'])):
    def __new__(cls, ref):
        name = ref.replace('$', '_')
        if name == 'False':
            name = 'false'
        elif name == 'True':
            name = 'true'
        elif name == 'None':
            name = 'none'
        return super(Identifier, cls).__new__(cls, ref, name)

def make_enum_constructor_fn(enum_type, constructor, type_refs):
    # A constant
    if len(constructor.fields) == 0:
        return AikenEnumValue(constructor.index, [])
    def constructor_fn(*args):
        return AikenEnumValue(constructor.index, args)
    constructor_fn.__name__ = constructor.name
    return constructor_fn

def make_module(module_name, module_dict, type_refs):
    # namedtuple fields have to be valid Python identifiers
    identifiers = [Identifier(ref) for ref in module_dict.keys()]
    identifiers.sort()
    Module = make_dataclass(module_name, [(i.name, Any) for i in identifiers])
    values = []
    for (ref, name) in identifiers:
        value = module_dict[ref]
        if isinstance(value, dict):
            values.append(make_module(name, value, type_refs))
        else:
            if isinstance(value, AikenEnumType):
                TypeModule = make_dataclass(name, [(Identifier(constructor.name).name, Any) for constructor in value.constructors])
                values.append(TypeModule(*[make_enum_constructor_fn(value, constructor, type_refs) for constructor in value.constructors]))
            else:
                values.append(value)
    return Module(*values)

def make_modules(type_defs):
    # we want to create nested module structure using dynamically created namedtuples
    top_level = {}
    for type_path_str, type_definition in type_defs.items():
        # in blueprint the path is separated by '/'
        type_path = type_path_str.split('/')
        module_path = type_path[:-1]
        type_name = type_path[-1]
        curr_parent = top_level
        for module_name in module_path:
            if module_name not in curr_parent:
                curr_parent[module_name] = {}
            curr_parent = curr_parent[module_name]
        curr_parent[type_name] = type_definition
    return make_module('blueprint', top_level, type_defs)

def Blueprint(module_name, function_name, aiken_project_directory=None, debug=True):
    blueprint_json = BlueprintJSON(module_name, function_name, aiken_project_directory)
    top_level = make_modules(blueprint_json.definitions)

    # We want to add __call__ to the module so it is really a blueprint 
    def eval_aiken_fn(self, *params):
        type_refs = blueprint_json.definitions
        try:
            terms = [AikenTerm.from_typed_value(arg, type_refs[type_ref], type_refs) for ((name, type_ref), arg) in zip(blueprint_json.parameters, params)]
        except Exception as e:
            if debug:
                print(f"Failed to parse arguments: {params}")
                print(f"Expected types: {blueprint_json.parameters}")
            raise e

        args_str = ' '.join([f"'{p.to_uplc().dumps()}'" for p in terms])
        response = json.loads(run_command(f"aiken uplc eval -c <(echo '{blueprint_json.compiled_code}') {args_str}"))
        Response = namedtuple('Response', ['result', 'cpu', 'mem'])

        source = f"(program 0.0.0 {response['result']})"
        program = uplc.tools.parse(source)
        result = program.term.value
        return Response(result, response['cpu'], response['mem'])

    # Let's copy everything from regular module and add __call__:
    attrs = [i for i in top_level.__annotations__.items()]
    BlueprintModule = make_dataclass(
        cls_name=f'Blueprint_{module_name}_{function_name}',
        fields=[(i[0], Any) for i in attrs],
        namespace={'__call__': eval_aiken_fn},
        frozen=True,
    )
    return BlueprintModule(*[getattr(top_level, i[0]) for i in attrs])

# blueprint = Blueprint("cheque", "is_one")
# print(blueprint)
# print(blueprint(1))
# 
# accept_bool_json = BlueprintJSON("cheque", "accept_bool")
# print(accept_bool_json.definitions)
# accept_bool = Blueprint("cheque", "accept_bool")
# print(accept_bool(False))
# print(accept_bool(True))
# 
# hello_json = BlueprintJSON("hello", "greet")
# print(hello_json.definitions)
# 
# blueprint = Blueprint("hello", "greet")
# print(blueprint(blueprint.hello.Entity.Person("paluh")))
# print(blueprint(blueprint.hello.Entity.Planet(blueprint.hello.Planet.Mercury)))
