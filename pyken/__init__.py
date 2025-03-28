import json
from collections import namedtuple
from dataclasses import make_dataclass
from typing import Any
import random
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

def not_implemented_error(msg):
    raise NotImplementedError(msg)

# Non parametric "well-known" types:
AikenSimpleType = namedtuple('AikenSimpleType', ['name', 'random'])
AikenBoolType = AikenSimpleType("Bool", lambda _type_refs: random.choice([True, False]))
AikenByteArrayType = AikenSimpleType("ByteArray", lambda _type_refs: bytes(random.randint(0, 255) for _ in range(random.randint(0, 32))))
AikenDataType = AikenSimpleType("Data", lambda _type_refs: not_implemented_error("Data type is not supported"))
AikenIntType = AikenSimpleType("Integer", lambda _type_refs: random.randint(-1000000, 1000000))
AikenStringType = AikenSimpleType("String", lambda _type_refs: ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(random.randint(0, 32))))

# Parametric "well-known" types:
class AikenListType(namedtuple('AikenListType', ['name', 'a'])):
    __slots__ = ()
    def __new__(cls, t_ref, type_refs):
        name = f"List<{t_ref}>"
        return super(AikenListType, cls).__new__(cls, name, t_ref)

    def random(self, type_refs):
        length = random.randint(0, 5)
        return [type_refs[self.a].random() for _ in range(length)]

class AikenPairType(namedtuple('AikenPairType', ['name', 'fst', 'snd'])):
    __slots__ = ()
    def __new__(cls, fst, snd):
        name = f"Pair<{fst.name}, {snd.name}>"
        return super(AikenPairType, cls).__new__(cls, name, fst, snd)
    def random(self, type_refs):
        return AikenPairValue(type_refs[self.fst].random(), type_refs[self.snd].random())

class AikenTupleType(namedtuple('AikenTupleType', ['name', 'fields'])):
    __slots__ = ()
    def __new__(cls, fields):
        name = f"Tuple<{', '.join(t_ref for t_ref in fields)}>"
        return super(AikenTupleType, cls).__new__(cls, name, fields)
    def random(self, type_refs):
        return tuple(type_refs[field].random() for field in self.fields)

# User defined types:
AikenFieldType = namedtuple('AikenFieldType', ['name', 'type'])

class AikenEnumConstructorType(namedtuple('AikenEnumConstructorType', ['name', 'index', 'fields'])):
    def random(self, type_refs):
        if len(self.fields) == 0:
            return AikenEnumValue(self.index, [])
        field_values = []
        for field_type_ref in self.fields:
            field_type = type_refs[field_type_ref]
            field_values.append(field_type.random(type_refs))
        return AikenEnumValue(self.index, field_values)

class AikenEnumType(namedtuple('AikenEnumType', ['name', 'constructors'])):
    def random(self, type_refs):
        constructor = random.choice(self.constructors)
        return constructor.random(type_refs)

# Most Aiken values can be derived directly through casting
# from Python values.
# Please note that in pyken we know the type of the value
# into which we want to cast during the contraction
# of the `AikenTerm` (so for example we know
# that a given tuple should be interpreted as an `AikenTupleType`
# and not as an `AikenPairType`).
# The only exception is the `AikenEnumValue` which is a bit
# more complex and has to be handled separately.

class AikenEnumValue(namedtuple('AikenEnumValue', ['index', 'fields'])):
    def random(self, type_refs):
        # This should never be called directly - enum values get their random
        # generation from their constructors
        raise NotImplementedError("Random generation should be handled by enum constructors")

class AikenPairValue(namedtuple('AikenPairValue', ['fst', 'snd'])):
    def random(self, type_refs):
        return AikenPairValue(
            type_refs[self.fst].random(type_refs),
            type_refs[self.snd].random(type_refs)
        )

class AikenTerm(namedtuple('AikenTerm', ['value', 'type', 'type_refs'])):
    @staticmethod
    def from_typed_value(python_value, aiken_type, type_refs):
        if isinstance(python_value, AikenTerm):
            if python_value.type == aiken_type:
                return python_value
            else:
                raise ValueError(f"Expecting a value of type {aiken_type}, got {python_value}")
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

# At the type level we don't resolve references to the other
# types because types can be mutually or even self recursive.
# We will resolve them at the term level as we can assume
# that the value is already well-formed.
def parse_type_reference(reference_str, valid_refs):
    if not reference_str.startswith("#/definitions/"):
        raise ValueError(f"Unknown reference: {reference_str}")
    def_reference = reference_str[len("#/definitions/"):].replace("~1", "/")
    if def_reference not in valid_refs:
        raise ValueError(f"Unknown reference: {reference_str}, {def_reference}, {valid_refs}")
    return def_reference

def parse_constructor(constructor, index, valid_refs):
    title = constructor['title']
    fields = [parse_type_reference(field['$ref'], valid_refs) for field in constructor['fields']]
    return AikenEnumConstructorType(title, index, fields)

def parse_definition(ref, definition, valid_refs):
    if 'dataType' in definition:
        if definition['dataType'] == 'integer':
            return AikenIntType
        elif definition['dataType'] == 'bytes':
            return AikenByteArrayType
        elif definition['dataType'] == 'list':
            # If a list contains only a single item element then it is really a list type.
            # Otherwise it is a tuple type.
            if len(definition['items']) == 1:
                ref_str = definition['items']['$ref']
                return AikenListType(parse_type_reference(ref_str, valid_refs))
            else:
                references = [parse_type_reference(item['$ref'], valid_refs) for item in definition['items']]
                return AikenTupleType(references, valid_refs)
        elif definition['dataType'] == '#string':
            return AikenStringType
    elif 'anyOf' in definition:
        title = definition.get('title', ref)
        if (title == 'Bool'
            and [c['title'] for c in definition['anyOf']] == ['False', 'True']
            and [len(c['fields']) for c in definition['anyOf']] == [0, 0]):
            return AikenBoolType
        constructors = [parse_constructor(constructor, index, valid_refs) for index, constructor in enumerate(definition['anyOf'])]
        return AikenEnumType(title, constructors)
    raise ValueError(f"Unknown definition: {definition}")

class BlueprintJSON(namedtuple('BlueprintJSON', ['name', 'parameters', 'definitions', 'compiled_code', 'hash'])):
    __slots__ = ()

    def __new__(cls, module_name, function_name, aiken_project_directory=None, debug=True):
        project_directory = f"{aiken_project_directory}" if aiken_project_directory else ""
        blueprint_json = json.loads(run_command(f"aiken export --module {module_name} --name {function_name} {project_directory}", debug=debug))
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
        valid_refs = set(definitions.keys())
        name = blueprint_json['name']
        parameters = [BlueprintJSON._parse_parameter(parameter, valid_refs) for parameter in blueprint_json['parameters']]
        type_refs = {}
        for ref, definition in definitions.items():
            type_refs[ref] = parse_definition(ref, definition, valid_refs)
        compiled_code = blueprint_json['compiledCode']
        hash = blueprint_json['hash']
        return super(BlueprintJSON, cls).__new__(cls, name, parameters, type_refs, compiled_code, hash)

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

# Beside just a constructor function which can be called directly
# like: `hello.Entity.Person("Full Name")` we want to also expose
# a random generator for values.
class ConstructorFnProxy:
    def __init__(self, constructor, random_fn):
        self.constructor = constructor
        self.random = staticmethod(random_fn)

    def __call__(self, *args, **kwargs):
        return self.constructor(*args, **kwargs)

def make_enum_constructor_fn(enum_type, constructor, type_refs):
    # A constant
    if len(constructor.fields) == 0:
        value = AikenEnumValue(constructor.index, [])
        value.random = lambda: value
        return value

    def constructor_fn(*args):
        return AikenEnumValue(constructor.index, args)

    constructor_fn.__name__ = constructor.name
    constructor_fn.random = lambda: constructor.random(type_refs)
    return constructor_fn

def make_module(module_name, module_dict, type_refs):
    identifiers = [Identifier(ref) for ref in module_dict.keys()]
    identifiers.sort()
    Module = make_dataclass(module_name, [(i.name, Any) for i in identifiers])
    values = []
    for (ref, name) in identifiers:
        module_attr = module_dict[ref]
        if isinstance(module_attr, dict):
            values.append(make_module(name, module_attr, type_refs))
        else:
            if isinstance(module_attr, AikenEnumType):
                attrs_annotations = [(Identifier(constructor.name).name, Any) for constructor in module_attr.constructors]
                attrs_annotations.append(('random', Any))
                TypeModule = make_dataclass(name, attrs_annotations)
                attrs = [make_enum_constructor_fn(module_attr, constructor, type_refs) for constructor in module_attr.constructors]
                attrs.append(lambda module_attr=module_attr: module_attr.random(type_refs))
                type_module = TypeModule(*attrs)
                values.append(type_module)
            elif module_attr == AikenIntType:
                values.append(int)
            elif module_attr == AikenByteArrayType:
                values.append(bytes)
            elif module_attr == AikenBoolType:
                values.append(bool)
            elif module_attr == AikenStringType:
                values.append(str)
            elif isinstance(module_attr, AikenListType):
                values.append(list)
            elif isinstance(module_attr, AikenTupleType):
                values.append(tuple)
            elif isinstance(module_attr, AikenPairType):
                values.append(AikenPairValue)
            else:
                raise ValueError(f"The module_attr {module_attr} has an unknown type: {type(module_attr)}")
    return Module(*values)

def make_modules(type_defs):
    # Create a nested module structure reflecting the Aiken type definitions
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
    blueprint_json = BlueprintJSON(module_name, function_name, aiken_project_directory, debug=debug)
    top_level = make_modules(blueprint_json.definitions)

    def type_ref_to_type(type_ref, top_level):
        type_ref_parts = type_ref.split('/')
        curr = top_level
        for part in type_ref_parts:
            curr = getattr(curr, part)
        return curr

    # We want to add __call__ to the root object to FFI into
    # the compiled Aiken function.
    def eval_aiken_fn(self, *params):
        type_refs = blueprint_json.definitions
        try:
            param_terms = [AikenTerm.from_typed_value(arg, type_refs[type_ref], type_refs) for ((name, type_ref), arg) in zip(blueprint_json.parameters, params)]
        except Exception as e:
            if debug:
                print(f"Failed to parse arguments: {params}")
                print(f"Expected types: {blueprint_json.parameters}")
            raise e

        args_str = ' '.join([f"'{p.to_uplc().dumps()}'" for p in param_terms])
        response = json.loads(run_command(f"aiken uplc eval -c <(echo '{blueprint_json.compiled_code}') {args_str}", debug=debug))
        Response = namedtuple('Response', ['result', 'cpu', 'mem'])

        source = f"(program 0.0.0 {response['result']})"
        program = uplc.tools.parse(source)
        result = program.term.value
        return Response(result, response['cpu'], response['mem'])
    # Let's build annotations dynamically which can be attached
    # to the function. This is useful for the IDEs to provide
    # type hints.
    # param_annotations = {name: type_ref_to_type(type_ref, top_level) for (name, type_ref) in blueprint_json.parameters}
    # eval_aiken_fn.__annotations__ = param_annotations

    # Let's copy everything from regular module and add __call__:
    attrs = [i for i in top_level.__annotations__.items()]
    BlueprintModule = make_dataclass(
        cls_name=f'Blueprint_{module_name}_{function_name}',
        fields=[(i[0], Any) for i in attrs],
        namespace={'__call__': eval_aiken_fn},
        frozen=True,
    )
    return BlueprintModule(*[getattr(top_level, i[0]) for i in attrs])

