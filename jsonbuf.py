#!/usr/bin/env python
# encoding: utf-8
from __future__ import print_function
import lxml.etree as etree
import os.path as p
import json, io, struct, os, re

JSONTYPE_double = 'double'
JSONTYPE_float = 'float'
JSONTYPE_ushort = 'ushort'
JSONTYPE_short = 'short'
JSONTYPE_uint = 'uint'
JSONTYPE_int = 'int'
JSONTYPE_ulong = 'ulong'
JSONTYPE_long = 'long'

JSONTYPE_byte = 'byte'
JSONTYPE_int8 = 'int8'
JSONTYPE_int16 = 'int16'
JSONTYPE_int32 = 'int32'
JSONTYPE_int64 = 'int64'
JSONTYPE_uint8 = 'uint8'
JSONTYPE_uint16 = 'uint16'
JSONTYPE_uint32 = 'uint32'
JSONTYPE_uint64 = 'uint64'
JSONTYPE_float32 = 'float32'
JSONTYPE_float64 = 'float64'
JSONTYPE_string = 'string'
JSONTYPE_bool = 'bool'

UINT16_MAX = (1 << 16) - 1
UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1

class Descriptor(object):
    def __init__(self, tag):
        self.tag = tag

class FieldDescriptor(Descriptor):
    def __init__(self):
        super(FieldDescriptor, self).__init__('field')
        self.name = ''
        self.type = ''
        self.enum = ''
        self.descriptor = None # type: Descriptor

class DictionaryDescriptor(Descriptor):
    def __init__(self):
        super(DictionaryDescriptor, self).__init__('dict')
        self.type = ''
        self.key = JSONTYPE_string
        self.descriptor = None # type: ClassDescriptor

class ArrayDescriptor(Descriptor):
    def __init__(self):
        super(ArrayDescriptor, self).__init__('array')
        self.type = ''
        self.mutable = False
        self.descriptor = None # type: ClassDescriptor

class ClassDescriptor(Descriptor):
    def __init__(self):
        super(ClassDescriptor, self).__init__('class')
        self.name = ''
        self.fields = [] # type: list[FieldDescriptor]

class JsonEnum(object):
    def __init__(self):
        self.full_type = ''
        self.type = ''
        self.cases = {}
        self.names = {}

    def fill(self, data): # type: (dict)->None
        self.full_type = data['name'] # type: str
        self.type = self.full_type.split('.')[-1]
        for case in data['cases']:
            self.cases[case['name']] = case['value']
            self.names[case['value']] = case['name']

class JsonbufSchema(object):
    def __init__(self):
        self.descriptor = None # type: Descriptor

    @staticmethod
    def check_type(type):
        assert 'JSONTYPE_{}'.format(type) in globals(), 'JSONTYPE_{}'.format(type)

    def load(self, filename):
        schema = etree.parse(filename).getroot()
        self.descriptor = self.decode(schema, attr={})
        return self.descriptor

    def dumps(self):
        schema = self.encode(descriptor=self.descriptor, attr={})
        return etree.tostring(schema, pretty_print=True, encoding='utf-8').decode('utf-8')

    def dump(self, filename):
        schema = self.encode(descriptor=self.descriptor, attr={})
        with open(filename, 'w') as fp:
            content = etree.tostring(schema, pretty_print=True, encoding='utf-8').decode('utf-8')
            fp.write(content)
            print('>>> {}'.format(p.abspath(fp.name)))
            print(content)

    def encode(self, descriptor, attr): # type: (Descriptor, dict)->etree.Element
        schema = etree.Element(descriptor.tag)
        if isinstance(descriptor, ArrayDescriptor) or isinstance(descriptor, DictionaryDescriptor):
            schema.set('type', descriptor.type)
            if isinstance(descriptor, ArrayDescriptor):
                if descriptor.mutable: schema.set('mutable', descriptor.mutable)
            if descriptor.type == 'class':
                assert isinstance(descriptor.descriptor, ClassDescriptor)
                schema.append(self.encode(descriptor.descriptor, attr=attr))
            elif descriptor.type == 'array':
                assert isinstance(descriptor.descriptor, ArrayDescriptor)
                schema.append(self.encode(descriptor.descriptor, attr=attr))
            elif descriptor.type == 'dict':
                assert isinstance(descriptor.descriptor, DictionaryDescriptor)
                if descriptor.key != JSONTYPE_string: schema.set('key', descriptor.key)
                schema.append(self.encode(descriptor.descriptor, attr=attr))
            else:
                self.check_type(descriptor.type)
        elif isinstance(descriptor, ClassDescriptor):
            schema.set('name', descriptor.name)
            if descriptor.name not in attr:
                attr[descriptor.name] = schema
                assert descriptor.fields
                for field in descriptor.fields:
                    schema.append(self.encode(descriptor=field, attr=attr))
        elif isinstance(descriptor, FieldDescriptor):
            schema.set('type', descriptor.type)
            schema.set('name', descriptor.name or '')
            if descriptor.enum: schema.set('enum', descriptor.enum)
            if descriptor.type == 'class':
                assert isinstance(descriptor.descriptor, ClassDescriptor)
                schema.append(self.encode(descriptor.descriptor, attr=attr))
            elif descriptor.type == 'array':
                assert isinstance(descriptor.descriptor, ArrayDescriptor)
                schema.append(self.encode(descriptor.descriptor, attr=attr))
            elif descriptor.type == 'dict':
                assert isinstance(descriptor.descriptor, DictionaryDescriptor)
                schema.append(self.encode(descriptor.descriptor, attr=attr))

            else:
                self.check_type(descriptor.type)
        else:
            raise NotImplementedError('<{}/>'.format(descriptor.tag))
        return schema

    def decode(self, schema, attr): # type: (etree.Element, dict)->Descriptor
        tag = schema.tag
        if tag in ('array', 'dict'):
            type = schema.get('type')
            descriptor = None
            if type in ('class', 'array', 'dict'):
                nest_schema = schema[0]
                assert nest_schema.tag == type
                descriptor = self.decode(schema=nest_schema, attr=attr)
            else:
                self.check_type(type)
            if tag == 'array':
                array = ArrayDescriptor()
                array.descriptor = descriptor
                array.type = type
                array.mutable = schema.get('mutable', False)
                return array
            else:
                dictionary = DictionaryDescriptor()
                dictionary.descriptor = descriptor
                dictionary.type = type
                dictionary.key = schema.get('key', JSONTYPE_string)
                return dictionary
        elif tag == 'class':
            class_name = schema.get('name')
            if class_name in attr:
                cls = attr[class_name]
            else:
                cls = ClassDescriptor()
                cls.name = schema.get('name')
                attr[cls.name] = cls
                for item in schema.xpath('./*'):
                    assert item.tag == 'field'
                    field = self.decode(schema=item, attr=attr)
                    cls.fields.append(field)
            return cls
        elif tag == 'field':
            field = FieldDescriptor()
            field.name = schema.get('name')
            field.type = schema.get('type')
            field.enum = schema.get('enum')
            if field.type in ('class', 'array', 'dict'):
                nest_schema = schema[0]
                assert nest_schema.tag == field.type
                field.descriptor = self.decode(schema=nest_schema, attr=attr)
            else:
                self.check_type(field.type)
            return field
        else:
            raise NotImplementedError('<{}/> not supported'.format(tag))

class JsonbufSerializer(object):
    def __init__(self, schema, class_nullable=True, enable_default=True, verbose=True):
        self.schema = schema # type: Descriptor
        self.class_nullable = class_nullable
        self.enable_default = enable_default
        self.verbose = verbose
        self.enums = {} # type: dict[str, JsonEnum]
        self.context = None
        self.endian = '<'
        self.__setup()

    def __setup(self):
        config_path = p.join(p.dirname(p.abspath(__file__)), 'jsonbuf.json')
        if p.exists(config_path):
            data = json.load(fp=open(config_path, 'r')) # type: dict
            for definition in data.get('enums', []):
                enum = JsonEnum()
                enum.fill(data=definition)
                self.enums[enum.type] = enum

    def serialize(self, fp): # type: (io.BytesIO)->None
        self.__encode(self.schema, value=self.context, buffer=fp)

    def deserilize(self, fp): # type: (io.BytesIO)->any
        self.context = self.__decode(self.schema, buffer=fp)
        return self.context

    @staticmethod
    def __get_default(type): # type: (str)->any
        if type == JSONTYPE_bool: return False
        if type.startswith('int'): return -1
        if type.startswith('uint'): return 0
        if type == JSONTYPE_byte: return 0
        if type in (JSONTYPE_ushort, JSONTYPE_ulong): return 0
        if type in (JSONTYPE_short, JSONTYPE_long): return -1
        if type == JSONTYPE_double or type.startswith('float'): return 0.0
        return None

    @staticmethod
    def __parse_key(value, type): # type: (str, str)->any
        if type.startswith('int') or type.startswith('uint') \
                or type in (JSONTYPE_byte, JSONTYPE_short, JSONTYPE_ushort, JSONTYPE_long, JSONTYPE_ulong): return int(value)
        if type.startswith('float') or type == JSONTYPE_double: return float(value)
        assert type == JSONTYPE_string
        return value

    def __encode_v(self, value, type, buffer): # type: (any, str, io.BytesIO)->None
        if type == JSONTYPE_bool:
            buffer.write(struct.pack('b', 1 if value else 0))
        elif type == JSONTYPE_int8:
            buffer.write(struct.pack('b', value))
        elif type in (JSONTYPE_uint8, JSONTYPE_byte):
            buffer.write(struct.pack('B', value))
        elif type in (JSONTYPE_int16, JSONTYPE_short):
            buffer.write(struct.pack(self.endian + 'h', value))
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort):
            buffer.write(struct.pack(self.endian + 'H', value))
        elif type in (JSONTYPE_int32, JSONTYPE_int):
            buffer.write(struct.pack(self.endian + 'i', value))
        elif type in (JSONTYPE_uint32, JSONTYPE_uint):
            buffer.write(struct.pack(self.endian + 'I', value))
        elif type in (JSONTYPE_int64, JSONTYPE_long):
            buffer.write(struct.pack(self.endian + 'q', value))
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong):
            buffer.write(struct.pack(self.endian + 'Q', value))
        elif type in (JSONTYPE_float32, JSONTYPE_float):
            buffer.write(struct.pack(self.endian + 'f', value))
        elif type in (JSONTYPE_float64, JSONTYPE_double):
            buffer.write(struct.pack(self.endian + 'd', value))
        elif type == JSONTYPE_string:
            if not value:
                self.__encode_v(-1 if value is None else 0, type=JSONTYPE_int16, buffer=buffer)
            else:
                value = str(value)
                bin = value.encode('utf-8')
                self.__encode_v(len(bin), type=JSONTYPE_uint16, buffer=buffer)
                buffer.write(bin)
        else:
            raise NotImplementedError('Not support for encoding value[={}] with {!r} type'.format(value, type))

    def __decode_v(self, type, buffer): # type: (str, io.BytesIO)->any
        if type == JSONTYPE_bool:
            v, = struct.unpack('b', buffer.read(1))
            v = v != 0
        elif type == JSONTYPE_int8:
            v, = struct.unpack('b', buffer.read(1))
        elif type in (JSONTYPE_uint8, JSONTYPE_byte):
            v, = struct.unpack('B', buffer.read(1))
        elif type in (JSONTYPE_int16, JSONTYPE_short):
            v, = struct.unpack(self.endian + 'h', buffer.read(2))
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort):
            v, = struct.unpack(self.endian + 'H', buffer.read(2))
        elif type in (JSONTYPE_int32, JSONTYPE_int):
            v, = struct.unpack(self.endian + 'i', buffer.read(4))
        elif type in (JSONTYPE_uint32, JSONTYPE_uint):
            v, = struct.unpack(self.endian + 'I', buffer.read(4))
        elif type in (JSONTYPE_int64, JSONTYPE_long):
            v, = struct.unpack(self.endian + 'q', buffer.read(8))
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong):
            v, = struct.unpack(self.endian + 'Q', buffer.read(8))
        elif type in (JSONTYPE_float32, JSONTYPE_float):
            v, = struct.unpack(self.endian + 'f', buffer.read(4))
        elif type in (JSONTYPE_float64, JSONTYPE_double):
            v, = struct.unpack(self.endian + 'd', buffer.read(8))
        elif type == JSONTYPE_string:
            size = self.__decode_v(type=JSONTYPE_uint16, buffer=buffer)
            if size == UINT16_MAX: v = None
            else:
                v = buffer.read(size).decode('utf-8') if size > 0 else ''
        else:
            raise NotImplementedError('Not support for decoding value with {!r} type'.format(type))
        return v

    def __encode(self, schema, value, buffer): # type: (Descriptor, any, io.BytesIO)->None
        if isinstance(schema, ArrayDescriptor):
            if value is None:
                self.__encode_v(-1, type=JSONTYPE_int32, buffer=buffer)
                return
            assert isinstance(value, list)
            self.__encode_v(len(value), type=JSONTYPE_uint32, buffer=buffer)
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor) \
                       or isinstance(schema.descriptor, DictionaryDescriptor)
                for element in value:
                    self.__encode(schema.descriptor, value=element, buffer=buffer)
            else:
                for element in value:
                    self.__encode_v(element, type=schema.type, buffer=buffer)
        elif isinstance(schema, DictionaryDescriptor):
            if value is None:
                self.__encode_v(-1, type=JSONTYPE_int32, buffer=buffer)
                return
            assert isinstance(value, dict)
            self.__encode_v(len(value), type=JSONTYPE_uint32, buffer=buffer)
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor) \
                       or isinstance(schema.descriptor, DictionaryDescriptor)
                for k, v in value.items():
                    self.__encode_v(self.__parse_key(k, type=schema.key), type=schema.key, buffer=buffer)
                    self.__encode(schema.descriptor, value=v, buffer=buffer)
            else:
                for k, v in value.items():
                    self.__encode_v(self.__parse_key(k, type=schema.key), type=schema.key, buffer=buffer)
                    self.__encode_v(v, type=schema.type, buffer=buffer)
        elif isinstance(schema, ClassDescriptor):
            if self.class_nullable:
                if not value:
                    self.__encode_v(0, type=JSONTYPE_bool, buffer=buffer)
                    return
                self.__encode_v(1, type=JSONTYPE_bool, buffer=buffer)
            assert schema.fields and isinstance(value, dict), (schema, value)
            for field in schema.fields:
                field_value = value.get(field.name)
                if field_value is None and self.enable_default:
                    if self.verbose: print('{}:{}'.format(field.name, field.type), value)
                    field_value = self.__get_default(type=field.type)
                self.__encode(field, value=field_value, buffer=buffer)
        elif isinstance(schema, FieldDescriptor):
            if schema.type == 'class':
                assert isinstance(schema.descriptor, ClassDescriptor)
                self.__encode(schema.descriptor, value=value, buffer=buffer)
            elif schema.type == 'array':
                assert isinstance(schema.descriptor, ArrayDescriptor)
                self.__encode(schema.descriptor, value=value, buffer=buffer)
            elif schema.type == 'dict':
                assert isinstance(schema.descriptor, DictionaryDescriptor)
                self.__encode(schema.descriptor, value=value, buffer=buffer)
            else:
                if schema.enum:
                    v = self.enums[schema.enum].cases[value]
                    self.__encode_v(v, type=schema.type, buffer=buffer)
                else:
                    self.__encode_v(value, type=schema.type, buffer=buffer)

    def __decode(self, schema, buffer):
        if isinstance(schema, ArrayDescriptor):
            size = self.__decode_v(JSONTYPE_uint32, buffer=buffer)
            if size == UINT32_MAX: return None
            elements = []
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor) \
                       or isinstance(schema.descriptor, DictionaryDescriptor)
                for _ in range(size):
                    elements.append(self.__decode(schema.descriptor, buffer=buffer))
            else:
                for _ in range(size):
                    elements.append(self.__decode_v(schema.type, buffer=buffer))
            return elements
        elif isinstance(schema, DictionaryDescriptor):
            size = self.__decode_v(JSONTYPE_uint32, buffer=buffer)
            if size == UINT32_MAX: return None
            data = {}
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor) \
                       or isinstance(schema.descriptor, DictionaryDescriptor)
                for _ in range(size):
                    key = self.__decode_v(schema.key, buffer=buffer)
                    data[key] = self.__decode(schema.descriptor, buffer=buffer)
            else:
                for _ in range(size):
                    key = self.__decode_v(schema.key, buffer=buffer)
                    data[key] = self.__decode_v(schema.type, buffer=buffer)
            return data
        elif isinstance(schema, ClassDescriptor):
            if self.class_nullable:
                if self.__decode_v(JSONTYPE_bool, buffer=buffer) == 0: return None
            obj = {}
            assert schema.fields
            for field in schema.fields:
                obj[field.name] = self.__decode(field, buffer=buffer)
            return obj
        elif isinstance(schema, FieldDescriptor):
            if schema.type == 'array':
                assert isinstance(schema.descriptor, ArrayDescriptor)
                return self.__decode(schema.descriptor, buffer=buffer)
            elif schema.type == 'class':
                assert isinstance(schema.descriptor, ClassDescriptor)
                return self.__decode(schema.descriptor, buffer=buffer)
            elif schema.type == 'dict':
                assert isinstance(schema.descriptor, DictionaryDescriptor)
                return self.__decode(schema.descriptor, buffer=buffer)
            else:
                v = self.__decode_v(schema.type, buffer=buffer)
                return self.enums[schema.enum].names[v] if schema.enum else v

class Commands(object):
    serialize = 'serialize'
    deserialize = 'deserialize'

    @classmethod
    def get_choices(cls):
        choices = []
        for k, v in vars(cls).items():
            if k == v: choices.append(v)
        return choices

def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--command', '-c', choices=Commands.get_choices(), default=Commands.serialize)
    arguments.add_argument('--class-nullable', action='store_true', help='allow class object encoded to null value')
    arguments.add_argument('--schema', '-s', help='data structure definition')
    arguments.add_argument('--output', '-o', default='.', help='path for saving generated files')
    arguments.add_argument('--verbose', '-v', action='store_true', help='enable verbose printing')
    arguments.add_argument('--file', '-f', help='intput file')
    options = arguments.parse_args(sys.argv[1:])

    script_path = p.dirname(p.abspath(__file__))

    output = p.abspath(options.output)
    if not p.exists(output): os.makedirs(output)

    filename = p.basename(options.file) # type: str
    name = re.sub(r'\.[^.]+$', '', filename)

    schema_path = options.schema # type: str
    if not schema_path:
        schema_path = p.join(script_path, 'schemas/{}.xml'.format(name))
        assert p.exists(schema_path), 'NOT_FOUND {}'.format(schema_path)
    print('[F] {}'.format(options.file))
    print('[S] {}'.format(schema_path))
    command = options.command # type: str
    schema = JsonbufSchema()
    descriptor = schema.load(filename=schema_path)
    serializer = JsonbufSerializer(schema=descriptor, class_nullable=options.class_nullable, verbose=options.verbose)
    print(schema.dumps())
    if command == Commands.serialize:
        assert options.file and re.search(r'\.json$', options.file)
        serializer.context = json.load(fp=open(options.file, 'r'))
        with open('{}/{}.bytes'.format(output, name), 'wb') as fp:
            serializer.serialize(fp)
            print('>>> {} {:,}'.format(p.abspath(fp.name), fp.tell()))
    elif command == Commands.deserialize:
        assert options.file and re.search(r'\.bytes$', options.file)
        data = serializer.deserilize(fp=open(options.file, 'rb'))
        content = json.dumps(data, indent=4, ensure_ascii=False)
        with open('{}/{}.json'.format(output, name), 'w') as fp:
            fp.write(content)
            print('>>> {}'.format(p.abspath(fp.name)))
            print(content)
    print()

if __name__ == '__main__':
    main()

