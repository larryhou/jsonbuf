#!/usr/bin/env python
# encoding: utf-8

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

class CppGenerator(object):
    def __init__(self, schema, output):
        self.schema = schema  # type: JsonbufSchema
        self.bridges = JsonbufBridges()
        self.indent = '    '
        self.__hpp = CodeWriter(filename=p.join(output, '{}.h'.format(self.schema.name)))
        self.__cpp = CodeWriter(filename=p.join(output, '{}.cpp'.format(self.schema.name)))

    @property
    def filenames(self): return self.__hpp.filename, self.__cpp.filename

    def __write(self, line, fp=None):
        if not fp: fp = self.__cpp
        fp.write(line)
        fp.write('\n')
        print(line)

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
        self.__hpp.write('#include "jsonbuf.h"')
        self.__hpp.write('')
        self.__hpp.write('#include <string>')
        self.__hpp.write('#include <vector>')
        self.__hpp.write('#include <map>')
        self.__hpp.write('')
        self.__cpp.write('#include "{}.h"'.format(self.schema.name))
        self.__cpp.write('')
        uniques = []
        count = self.schema.classes['count'] # type: int
        for n in range(count):
            cls = self.schema.classes[n] # type: ClassDescriptor
            ns = cls.namespace if cls.namespace else 'jsonbuf.{}'.format(self.schema.name)
            components = ns.split('.')
            for name in components:
                self.__hpp.write('namespace %s { ' % name, newline=False)
            self.__hpp.write('')
            if ns not in uniques:
                self.__cpp.write('using namespace {};\n'.format(ns.replace('.', '::')))
                uniques.append(ns)
            self.__generate_class(cls, indent=self.indent)
            self.__hpp.write('{}\n'.format('}' * len(components)))
        self.__hpp.close(True)
        self.__cpp.close(True)

    @staticmethod
    def __ctype(type): # type: (str)->str
        if type == JSONTYPE_int8: return 'int8_t'
        if type in (JSONTYPE_uint8, JSONTYPE_byte): return 'uint8_t'
        if type in (JSONTYPE_short, JSONTYPE_int16): return 'int16_t'
        if type in (JSONTYPE_ushort, JSONTYPE_uint16): return 'uint16_t'
        if type in (JSONTYPE_ulong, JSONTYPE_uint64): return 'uint64_t'
        if type in (JSONTYPE_long, JSONTYPE_int64): return 'int64_t'
        if type in (JSONTYPE_int, JSONTYPE_int32): return 'int32_t'
        if type in (JSONTYPE_uint, JSONTYPE_uint32): return 'uint32_t'
        if type in (JSONTYPE_float, JSONTYPE_float32): return 'float'
        if type in (JSONTYPE_double, JSONTYPE_float64): return 'double'
        if type in (JSONTYPE_double, JSONTYPE_string): return 'std::string'
        return type

    def __rtype(self, type):
        if isinstance(type, ClassDescriptor): return type.name
        if isinstance(type, ArrayDescriptor):
            return 'std::vector<{}>'.format(self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type))
        if isinstance(type, DictionaryDescriptor):
            return 'std::map<{},{}>'\
                .format(self.__ctype(type.key), self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type))
        if isinstance(type, FieldDescriptor):
            if type.descriptor: return self.__rtype(type=type.descriptor)
            return self.__ctype(type.type)
        assert isinstance(type, str)
        return self.__ctype(type)

    def __generate_class(self, cls, indent=''):
        self.__hpp.write('{}class {}: public IJsonbuf'.format(indent, cls.name))
        self.__hpp.write('{}{{'.format(indent))
        self.__hpp.write('{}  public:'.format(indent))
        for filed in cls.fields:
            self.__hpp.write('{}    {} {};'.format(indent, self.__rtype(filed), filed.name))
        self.__hpp.write('')
        self.__hpp.write('{}  public:'.format(indent))
        self.__hpp.write('{}    void deserialize(JsonbufStream& decoder);'.format(indent))
        self.__generate_decode_method(cls, indent='')
        self.__cpp.write('')
        self.__hpp.write('{}    void serialize(JsonbufStream& encoder);'.format(indent))
        self.__generate_encode_method(cls, indent='')
        self.__cpp.write('')
        self.__hpp.write('{}}};'.format(indent))

    def __generate_decode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        self.__cpp.write('{}void {}::deserialize(JsonbufStream& decoder)'.format(indent, cls.name))
        self.__cpp.write('{}{{'.format(indent))
        index = IndexAttr(0)
        for field in cls.fields:
            self.__generate_decode_field(name=field.name, descriptor=field, indent=indent + self.indent, level=1, attr=index)
        self.__cpp.write('{}}}'.format(indent))

    def __generate_encode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        self.__cpp.write('{}void {}::serialize(JsonbufStream& encoder)'.format(indent, cls.name))
        self.__cpp.write('{}{{'.format(indent))
        index = IndexAttr(0)
        for field in cls.fields:
            self.__generate_encode_field(name=field.name, descriptor=field, indent=indent + self.indent, level=1, attr=index)
        self.__cpp.write('{}}}'.format(indent))

    @staticmethod
    def __get_decode_m(type):
        if type == JSONTYPE_bool: return 'read<bool>'
        elif type == JSONTYPE_int8: return 'read<int8_t>'
        elif type in (JSONTYPE_uint8, JSONTYPE_byte): return 'read<uint8_t>'
        elif type in (JSONTYPE_int16, JSONTYPE_short): return 'read<int16_t>'
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort): return 'read<uint16_t>'
        elif type in (JSONTYPE_int32, JSONTYPE_int): return 'read<int32_t>'
        elif type in (JSONTYPE_uint32, JSONTYPE_uint): return 'read<uint32_t>'
        elif type in (JSONTYPE_int64, JSONTYPE_long): return 'read<int64_t>'
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong): return 'read<uint64_t>'
        elif type in (JSONTYPE_float32, JSONTYPE_float): return 'read<float>'
        elif type in (JSONTYPE_float64, JSONTYPE_double): return 'read<double>'
        elif type == JSONTYPE_string: return 'read<std::string>'
        raise NotImplementedError('Type[={}] not supported'.format(type))

    @staticmethod
    def __get_encode_m(type):
        if type == JSONTYPE_bool: return 'write<bool>'
        elif type == JSONTYPE_int8: return 'write<int8_t>'
        elif type in (JSONTYPE_uint8, JSONTYPE_byte): return 'write<uint8_t>'
        elif type in (JSONTYPE_int16, JSONTYPE_short): return 'write<int16_t>'
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort): return 'write<uint16_t>'
        elif type in (JSONTYPE_int32, JSONTYPE_int): return 'write<int32_t>'
        elif type in (JSONTYPE_uint32, JSONTYPE_uint): return 'write<uint32_t>'
        elif type in (JSONTYPE_int64, JSONTYPE_long): return 'write<int64_t>'
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong): return 'write<uint64_t>'
        elif type in (JSONTYPE_float32, JSONTYPE_float): return 'write<float>'
        elif type in (JSONTYPE_float64, JSONTYPE_double): return 'write<double>'
        elif type == JSONTYPE_string: return 'write<std::string>'
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
            self.__cpp.write('{}{}.deserialize(decoder);'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = self.__local_name(attr.next)
            count = 'c{}'.format(index)
            element = 't{}'.format(index)
            self.__cpp.write('{}auto {} = decoder.{}();'.format(indent, count, self.__get_decode_m(JSONTYPE_uint)))
            # self.__cpp.write('{}{}.reserve({});'.format(indent, name, count))
            self.__cpp.write('{}if ({} == 0xFFFFFFFF) {{ {} = {}(); }} else {{'.format(indent, count, name, self.__rtype(descriptor)))
            self.__cpp.write('{}for (auto {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            self.__cpp.write('%s{' % indent)
            self.__cpp.write('{}    {} {};'.format(indent, self.__rtype(descriptor.descriptor if descriptor.descriptor else descriptor.type), element))
            if descriptor.descriptor:
                self.__generate_decode_field(element, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__cpp.write('{}    {} = decoder.{}();'.format(indent, element, self.__get_decode_m(descriptor.type)))
            self.__cpp.write('{}    {}.emplace_back({});'.format(indent, name, element))
            self.__cpp.write('%s}}' % indent)
        elif isinstance(descriptor, DictionaryDescriptor):
            index = self.__local_name(attr.next)
            count = 'c{}'.format(index)
            key = 'k{}'.format(index)
            val = 'v{}'.format(index)
            self.__cpp.write('{}auto {} = decoder.{}();'.format(indent, count, self.__get_decode_m(JSONTYPE_uint)))
            # self.__cpp.write('{}{}.reserve({});'.format(indent, name, count))
            self.__cpp.write('{}if ({} == 0xFFFFFFFF) {{ {} = {}(); }} else {{'.format(indent, count, name, self.__rtype(descriptor)))
            self.__cpp.write('{}for (auto {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            self.__cpp.write('%s{' % indent)
            self.__cpp.write('{}    {} {};'.format(indent, self.__rtype(descriptor.descriptor if descriptor.descriptor else descriptor.type), val))
            self.__cpp.write('{}    auto {} = decoder.{}();'.format(indent, key, self.__get_decode_m(descriptor.key)))
            if descriptor.descriptor:
                self.__generate_decode_field(val, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__cpp.write('{}    {} = decoder.{}();'.format(indent, val, self.__get_decode_m(descriptor.type)))
            self.__cpp.write('{}    {}.insert(std::make_pair({}, {}));'.format(indent, name, key, val))
            self.__cpp.write('%s}}' % indent)
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.__generate_decode_field(name=field.name, descriptor=field.descriptor, indent=indent, level=level, attr=attr)
            else:
                self.__cpp.write('{}{} = decoder.{}();'.format(indent, name, self.__get_decode_m(field.type)))

    def __generate_encode_field(self, name, descriptor, indent, level=0, attr=None): # type: (str, Descriptor, str, int, IndexAttr)->None
        if isinstance(descriptor, ClassDescriptor):
            self.__cpp.write('{}{}.serialize(encoder);'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = self.__local_name(attr.next)
            count = '{}.size()'.format(name)
            static_cast_count = 'static_cast<{}>({})'.format(self.__ctype(JSONTYPE_uint32), count)
            element = '*{}'.format(index)
            self.__cpp.write('{}encoder.{}({});'.format(indent, self.__get_encode_m(JSONTYPE_uint), static_cast_count))
            self.__cpp.write('{}for (auto {} = {}.begin(); {} != {}.end(); {}++)'.format(indent, index, name, index, name, index))
            self.__cpp.write('%s{' % indent)
            if descriptor.descriptor:
                self.__generate_encode_field('({})'.format(element), descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__cpp.write('{}    encoder.{}({});'.format(indent, self.__get_encode_m(descriptor.type), element))
            self.__cpp.write('%s}' % indent)
        elif isinstance(descriptor, DictionaryDescriptor):
            index = self.__local_name(attr.next)
            count = '{}.size()'.format(name)
            static_cast_count = 'static_cast<{}>({})'.format(self.__ctype(JSONTYPE_uint32), count)
            pair = 'p{}'.format(index)
            self.__cpp.write('{}encoder.{}({});'.format(indent, self.__get_encode_m(JSONTYPE_uint), static_cast_count))
            self.__cpp.write('{}for (auto {} = {}.begin(); {} != {}.end(); {}++)'.format(indent, pair, name, pair, name, pair))
            self.__cpp.write('%s{' % indent)
            self.__cpp.write('{}    encoder.{}({}->first);'.format(indent, self.__get_encode_m(descriptor.key), pair))
            if descriptor.descriptor:
                self.__generate_encode_field('{}->second'.format(pair), descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__cpp.write('{}    encoder.{}({}->second);'.format(indent, self.__get_encode_m(descriptor.type), pair))
            self.__cpp.write('%s}' % indent)
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.__generate_encode_field(name=field.name, descriptor=field.descriptor, indent=indent, level=level, attr=attr)
            else:
                self.__cpp.write('{}encoder.{}({});'.format(indent, self.__get_encode_m(field.type), field.name))



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
        generator = CppGenerator(schema, output)
        generator.generate()
        print('>>> {}\n'.format(generator.filenames))

if __name__ == '__main__':
    main()
