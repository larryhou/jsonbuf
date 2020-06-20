#!/usr/bin/env python

from __future__ import print_function
from jsonbuf import *
import os.path as p
import typing

class IndexAttr(object):
    def __init__(self, value):
        self.__value = value
        self.__next = value

    @property
    def value(self): return self.__value

    @property
    def next(self):
        self.__next += 1
        return self.__next

class PyGenerator(object):
    def __init__(self, schema, output):
        self.schema = schema  # type: JsonbufSchema
        self.bridges = JsonbufBridges()
        self.indent = '    '
        self.__code = CodeWriter(filename=p.join(output, '{}.py'.format(self.schema.name)))

    @property
    def filename(self): return self.__code.filename

    def __get_namespaces(self, descriptor): # type: (Descriptor)->list[str]
        namespaces = []
        if isinstance(descriptor, ArrayDescriptor) or isinstance(descriptor, DictionaryDescriptor):
            if descriptor.descriptor:
                namespaces.extend(self.__get_namespaces(descriptor.descriptor))
        elif isinstance(descriptor, ClassDescriptor):
            for field in descriptor.fields:
                namespaces.extend(self.__get_namespaces(field))
        elif isinstance(descriptor, FieldDescriptor):
            if descriptor.descriptor:
                namespaces.extend(self.__get_namespaces(descriptor.descriptor))
            elif descriptor.enum:
                enum = self.bridges.enums[descriptor.enum]  # type: JsonbufEnumBridge
                namespaces.append(enum.namespace)
        return namespaces

    def generate(self):
        self.__code.write('from jsonbuf import *')
        self.__code.write('')
        count = self.schema.classes['count'] # type: int
        for n in range(count):
            cls = self.schema.classes[n] # type: ClassDescriptor
            self.__generate_class(cls, indent='')
        self.__code.close(True)

    @staticmethod
    def __get_default(type):  # type: (str)->any
        if type == JSONTYPE_bool: return False
        if type.startswith('int'): return -1
        if type.startswith('uint'): return 0
        if type == JSONTYPE_byte: return 0
        if type in (JSONTYPE_ushort, JSONTYPE_ulong): return 0
        if type in (JSONTYPE_short, JSONTYPE_long): return -1
        if type == JSONTYPE_double or type.startswith('float'): return 0.0
        if type == JSONTYPE_string: return '{!r}'.format('')
        if type == 'class': return 'None'
        if type == 'array': return '[]'
        if type == 'dict': return '{}'
        return None

    @staticmethod
    def __get_key(value, type):  # type: (str, str)->any
        if type.startswith('int') or type.startswith('uint') \
                or type in (JSONTYPE_byte, JSONTYPE_short, JSONTYPE_ushort, JSONTYPE_long, JSONTYPE_ulong): return 'int({})'.format(value)
        if type.startswith('float') or type == JSONTYPE_double: return 'float({})'.format(value)
        assert type == JSONTYPE_string
        return value

    @staticmethod
    def __ctype(type): # type: (str)->str
        if type == JSONTYPE_int8: return 'int'
        if type in (JSONTYPE_uint8, JSONTYPE_byte): return 'int'
        if type in (JSONTYPE_short, JSONTYPE_int16): return 'int'
        if type in (JSONTYPE_ushort, JSONTYPE_uint16): return 'int'
        if type in (JSONTYPE_ulong, JSONTYPE_uint64): return 'int'
        if type in (JSONTYPE_long, JSONTYPE_int64): return 'int'
        if type in (JSONTYPE_int, JSONTYPE_int32): return 'int'
        if type in (JSONTYPE_uint, JSONTYPE_uint32): return 'int'
        if type in (JSONTYPE_float, JSONTYPE_float32): return 'float'
        if type in (JSONTYPE_double, JSONTYPE_float64): return 'float'
        if type in (JSONTYPE_double, JSONTYPE_string): return 'str'
        return type

    def __rtype(self, type):
        if isinstance(type, ClassDescriptor): return type.name
        if isinstance(type, ArrayDescriptor):
            return 'list[{}]'.format(self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type))
        if isinstance(type, DictionaryDescriptor):
            return 'dict[{},{}]'\
                .format(self.__ctype(type.key), self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type))
        if isinstance(type, FieldDescriptor):
            if type.descriptor: return self.__rtype(type=type.descriptor)
            return self.__ctype(type.type)
        assert isinstance(type, str)
        return self.__ctype(type)

    def __generate_class(self, cls, indent=''):
        self.__code.write('{}class {}(IJsonbuf):'.format(indent, cls.name))
        self.__code.write('{}{}def __init__(self):'.format(indent, self.indent))
        for filed in cls.fields:
            self.__code.write('{}{}{}self.{} = {} # type: {}'.format(indent, self.indent, self.indent, filed.name, self.__get_default(filed.type), self.__rtype(filed)))
        self.__code.write('')
        self.__generate_decode_method(cls, indent=indent + self.indent)
        self.__code.write('')
        self.__generate_encode_method(cls, indent=indent + self.indent)
        self.__code.write('')

    def __generate_decode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        self.__code.write('{}def deserialize(self, decoder): # type: (JsonbufStream)->None'.format(indent, cls.name))
        index = IndexAttr(0)
        for field in cls.fields:
            self.__generate_decode_field(name=field.name, descriptor=field, indent=indent + self.indent, level=1, attr=index)

    def __generate_encode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        self.__code.write('{}def serialize(self, encoder): # type: (JsonbufStream)->None'.format(indent, cls.name))
        index = IndexAttr(0)
        for field in cls.fields:
            self.__generate_encode_field(name=field.name, descriptor=field, indent=indent + self.indent, level=1, attr=index)

    @staticmethod
    def __get_decode_m(type):
        if type == JSONTYPE_bool: return 'read_bool'
        elif type == JSONTYPE_int8: return 'read_int8'
        elif type in (JSONTYPE_uint8, JSONTYPE_byte): return 'read_uint8'
        elif type in (JSONTYPE_int16, JSONTYPE_short): return 'read_int16'
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort): return 'read_uint16'
        elif type in (JSONTYPE_int32, JSONTYPE_int): return 'read_int32'
        elif type in (JSONTYPE_uint32, JSONTYPE_uint): return 'read_uint32'
        elif type in (JSONTYPE_int64, JSONTYPE_long): return 'read_int64'
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong): return 'read_uint64'
        elif type in (JSONTYPE_float32, JSONTYPE_float): return 'read_float'
        elif type in (JSONTYPE_float64, JSONTYPE_double): return 'read_double'
        elif type == JSONTYPE_string: return 'read_string'
        raise NotImplementedError('Type[={}] not supported'.format(type))

    @staticmethod
    def __get_encode_m(type):
        if type == JSONTYPE_bool: return 'write_bool'
        elif type == JSONTYPE_int8: return 'write_int8'
        elif type in (JSONTYPE_uint8, JSONTYPE_byte): return 'write_uint8'
        elif type in (JSONTYPE_int16, JSONTYPE_short): return 'write_int16'
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort): return 'write_uint16'
        elif type in (JSONTYPE_int32, JSONTYPE_int): return 'write_int32'
        elif type in (JSONTYPE_uint32, JSONTYPE_uint): return 'write_uint32'
        elif type in (JSONTYPE_int64, JSONTYPE_long): return 'write_int64'
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong): return 'write_uint64'
        elif type in (JSONTYPE_float32, JSONTYPE_float): return 'write_float'
        elif type in (JSONTYPE_float64, JSONTYPE_double): return 'write_double'
        elif type == JSONTYPE_string: return 'write_string'
        raise NotImplementedError('Type[={}] not supported'.format(type))

    @staticmethod
    def __local_name(index): # type: (int)->str
        shift = ord('l') - 97
        value = ''
        while index > 0:
            c = index % 26
            index /= 26
            value += chr(((c + shift) % 26) + 97)
        return value


    def __generate_decode_field(self, name, descriptor, indent, level=0, attr=None): # type: (str, Descriptor, str, int, IndexAttr)->None
        if isinstance(descriptor, ClassDescriptor):
            self.__code.write('{}{}.deserialize(decoder)'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = self.__local_name(attr.next)
            count = 'c{}'.format(index)
            element = 't{}'.format(index)
            self.__code.write('{}{} = [] # type: {}'.format(indent, name, self.__rtype(descriptor)))
            self.__code.write('{}{} = decoder.{}()'.format(indent, count, self.__get_decode_m(JSONTYPE_uint)))
            self.__code.write('{}if {} != 0xFFFFFFFF:'.format(indent, count))
            indent += self.indent
            self.__code.write('{}for {} in range({}):'.format(indent, index, count))
            if descriptor.descriptor:
                self.__generate_decode_field(element, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}{}{} = decoder.{}()'.format(indent, self.indent, element, self.__get_decode_m(descriptor.type)))
            self.__code.write('{}{}{}.append({})'.format(indent, self.indent, name, element))
        elif isinstance(descriptor, DictionaryDescriptor):
            index = self.__local_name(attr.next)
            count = 'c{}'.format(index)
            key = 'k{}'.format(index)
            val = 'v{}'.format(index)
            self.__code.write('{}{} = {{}} # type: {}'.format(indent, name, self.__rtype(descriptor)))
            self.__code.write('{}{} = decoder.{}()'.format(indent, count, self.__get_decode_m(JSONTYPE_uint)))
            self.__code.write('{}if {} != 0xFFFFFFFF:'.format(indent, count))
            indent += self.indent
            self.__code.write('{}for {} in range({}):'.format(indent, index, count))
            if descriptor.descriptor:
                self.__generate_decode_field(val, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}{}{} = decoder.{}()'.format(indent, self.indent, val, self.__get_decode_m(descriptor.type)))
            self.__code.write('{}{}{}[{}] = {}'.format(indent, self.indent, name, key, val))
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.__generate_decode_field(name='self.{}'.format(field.name), descriptor=field.descriptor, indent=indent, level=level, attr=attr)
            else:
                self.__code.write('{}self.{} = decoder.{}()'.format(indent, name, self.__get_decode_m(field.type)))

    def __generate_encode_field(self, name, descriptor, indent, level=0, attr=None): # type: (str, Descriptor, str, int, IndexAttr)->None
        if isinstance(descriptor, ClassDescriptor):
            self.__code.write('{}{}.serialize(encoder)'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = self.__local_name(attr.next)
            count = 'len({})'.format(name)
            element = '{}'.format(index)
            self.__code.write('{}if {} is None:'.format(indent, name))
            self.__code.write('{}{}encoder.{}(-1)'.format(indent, self.indent, self.__get_encode_m(JSONTYPE_int)))
            self.__code.write('{}else:'.format(indent))
            indent += self.indent
            self.__code.write('{}encoder.{}({})'.format(indent, self.__get_encode_m(JSONTYPE_uint), count))
            self.__code.write('{}for {} in {}:'.format(indent, element, name))
            if descriptor.descriptor:
                self.__generate_encode_field('{}'.format(element), descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}{}encoder.{}({})'.format(indent, self.indent, self.__get_encode_m(descriptor.type), element))
        elif isinstance(descriptor, DictionaryDescriptor):
            index = self.__local_name(attr.next)
            count = 'len({})'.format(name)
            key = 'k{}'.format(index)
            val = 'v{}'.format(index)
            self.__code.write('{}if {} is None:'.format(indent, name))
            self.__code.write('{}{}encoder.{}(-1)'.format(indent, self.indent, self.__get_encode_m(JSONTYPE_int)))
            self.__code.write('{}else:'.format(indent))
            indent += self.indent
            self.__code.write('{}encoder.{}({})'.format(indent, self.__get_encode_m(JSONTYPE_uint), count))
            self.__code.write('{}for {},{} in {}.items():'.format(indent, key, val, name))
            self.__code.write('{}{}encoder.{}({})'.format(indent, self.indent, self.__get_encode_m(descriptor.key), self.__get_key(key, type=descriptor.key)))
            if descriptor.descriptor:
                self.__generate_encode_field(val, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}{}encoder.{}({})'.format(indent, self.indent, self.__get_encode_m(descriptor.type), val))
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.__generate_encode_field(name='self.{}'.format(field.name), descriptor=field.descriptor, indent=indent, level=level, attr=attr)
            else:
                self.__code.write('{}encoder.{}(self.{})'.format(indent, self.__get_encode_m(field.type), field.name))


def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--schema', '-s', nargs='+', required=True, help='data structure definition')
    arguments.add_argument('--output', '-o', default='.', help='path for saving generated files')
    arguments.add_argument('--verbose', '-v', action='store_true', help='enable verbose printing')
    options = arguments.parse_args(sys.argv[1:])

    output = p.abspath(options.output)
    if not p.exists(output): os.makedirs(output)
    for filename in options.schema:
        print('[S] {}'.format(p.abspath(filename)))
        schema = JsonbufSchema()
        schema.load(filename)
        generator = PyGenerator(schema, output)
        generator.generate()
        print('>>> {}\n'.format(generator.filename))

if __name__ == '__main__':
    main()
