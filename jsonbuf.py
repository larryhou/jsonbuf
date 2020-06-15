#!/usr/bin/env python
# encoding: utf-8
from __future__ import print_function
import lxml.etree as etree
import os.path as p
import json, io, struct, os

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
        self.descriptor = None # type: Descriptor

class DictionaryDescriptor(Descriptor):
    def __init__(self):
        super(DictionaryDescriptor, self).__init__('dict')
        self.type = ''
        self.descriptor = None # type: ClassDescriptor

class ArrayDescriptor(Descriptor):
    def __init__(self):
        super(ArrayDescriptor, self).__init__('array')
        self.type = ''
        self.descriptor = None # type: ClassDescriptor

class ClassDescriptor(Descriptor):
    def __init__(self):
        super(ClassDescriptor, self).__init__('class')
        self.name = ''
        self.fields = [] # type: list[FieldDescriptor]

class JsonbufSchema(object):
    def __init__(self):
        self.descriptor = None # type: Descriptor
        self.classes = [] # type: list[ClassDescriptor]

    @staticmethod
    def check_type(type):
        assert 'JSONTYPE_{}'.format(type) in globals(), 'JSONTYPE_{}'.format(type)

    def load(self, filename):
        schema = etree.parse(filename).getroot()
        self.descriptor, self.classes = self.decode(schema)
        return self.descriptor

    def dump(self, filename):
        schema = self.encode(descriptor=self.descriptor)
        with open(filename, 'w') as fp:
            content = etree.tostring(schema, pretty_print=True, encoding='utf-8').decode('utf-8')
            fp.write(content)
            print('>>> {}'.format(p.abspath(fp.name)))
            print(content)

    def encode(self, descriptor):
        schema = etree.Element(descriptor.tag)
        if isinstance(descriptor, ArrayDescriptor) or isinstance(descriptor, DictionaryDescriptor):
            schema.set('type', descriptor.type)
            if descriptor.type == 'class':
                assert isinstance(descriptor.descriptor, ClassDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            elif descriptor.type == 'array':
                assert isinstance(descriptor.descriptor, ArrayDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            elif descriptor.type == 'dict':
                assert isinstance(descriptor.descriptor, DictionaryDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            else:
                self.check_type(descriptor.type)
        elif isinstance(descriptor, ClassDescriptor):
            schema.set('name', descriptor.name)
            assert descriptor.fields
            for field in descriptor.fields:
                schema.append(self.encode(descriptor=field))
        elif isinstance(descriptor, FieldDescriptor):
            schema.set('type', descriptor.type)
            schema.set('name', descriptor.name or '')
            if descriptor.type == 'class':
                assert isinstance(descriptor.descriptor, ClassDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            elif descriptor.type == 'array':
                assert isinstance(descriptor.descriptor, ArrayDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            elif descriptor.type == 'dict':
                assert isinstance(descriptor.descriptor, DictionaryDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            else:
                self.check_type(descriptor.type)
        else:
            raise NotImplementedError('<{}/>'.format(descriptor.tag))
        return schema

    def decode(self, schema):
        classes = []
        tag = schema.tag
        if tag in ('array', 'dict'):
            type = schema.get('type')
            descriptor = None
            if type in ('class', 'array', 'dict'):
                nest_schema = schema[0]
                assert nest_schema.tag == type
                descriptor, subclasses = self.decode(schema=nest_schema)
                if subclasses: classes.extend(subclasses)
            else:
                self.check_type(type)
            if tag == 'array':
                array = ArrayDescriptor()
                array.descriptor = descriptor
                array.type = type
                return array, classes
            else:
                dictionary = DictionaryDescriptor()
                dictionary.descriptor = descriptor
                dictionary.type = type
                return dictionary, classes
        elif tag == 'class':
            cls = ClassDescriptor()
            cls.name = schema.get('name')
            for item in schema.xpath('./*'):
                assert item.tag == 'field'
                field, subclasses = self.decode(schema=item)
                if subclasses: classes.extend(subclasses)
                cls.fields.append(field)
            classes.append(cls)
            return cls, classes
        elif tag == 'field':
            field = FieldDescriptor()
            field.name = schema.get('name')
            field.type = schema.get('type')
            if field.type in ('class', 'array', 'dict'):
                nest_schema = schema[0]
                assert nest_schema.tag == field.type
                field.descriptor, subclasses = self.decode(schema=nest_schema)
                if subclasses: classes.extend(subclasses)
            else:
                self.check_type(field.type)
            return field, classes
        else:
            raise NotImplementedError('<{}/> not supported'.format(tag))

class JsonbufSerializer(object):
    def __init__(self, schema, class_nullable=True, default_enabled=True, verbose=True):
        self.schema = schema # type: Descriptor
        self.class_nullable = class_nullable
        self.default_enabled = default_enabled
        self.verbose = verbose
        self.context = None
        self.endian = '<'

    def load(self, filename):
        self.context = json.load(fp=open(filename, 'r'))

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
            assert schema.descriptor and isinstance(value, list)
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
            assert schema.descriptor and isinstance(value, dict)
            self.__encode_v(len(value), type=JSONTYPE_uint32, buffer=buffer)
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor) \
                       or isinstance(schema.descriptor, DictionaryDescriptor)
                for k, v in value.items():
                    self.__encode_v(k, type=JSONTYPE_string, buffer=buffer)
                    self.__encode(schema.descriptor, value=v, buffer=buffer)
            else:
                for k, v in value.items():
                    self.__encode_v(k, type=JSONTYPE_string, buffer=buffer)
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
                if field_value is None and self.default_enabled:
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
                    key = self.__decode_v(JSONTYPE_string, buffer=buffer)
                    data[key] = self.__decode(schema.descriptor, buffer=buffer)
            else:
                for _ in range(size):
                    key = self.__decode_v(JSONTYPE_string, buffer=buffer)
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
                return self.__decode_v(schema.type, buffer=buffer)

def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--file', '-f', required=True)
    arguments.add_argument('--schema', '-s', required=True)
    arguments.add_argument('--class-nullable', action='store_true')
    options = arguments.parse_args(sys.argv[1:])

    schema = JsonbufSchema()
    descriptor = schema.load(filename=options.schema)
    schema.dump(filename='test.xml')
    serializer = JsonbufSerializer(schema=descriptor, class_nullable=options.class_nullable)
    serializer.load(filename=options.file)
    buffer = io.BytesIO()
    serializer.serialize(fp=buffer)
    print(buffer, buffer.tell())

    buffer.seek(0)
    with open('data.bin', 'wb') as fp:
        fp.write(buffer.read())
    buffer.seek(0)
    data = serializer.deserilize(fp=buffer)
    print(json.dumps(data, indent=4, ensure_ascii=False))


if __name__ == '__main__':
    main()

