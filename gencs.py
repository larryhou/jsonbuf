#!/usr/bin/env python
# encoding: utf-8

from __future__ import print_function
from jsonbuf import *
import os.path as p

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

class CSharpGenerator(object):
    def __init__(self, schema, output):
        self.schema = schema  # type: JsonbufSchema
        self.bridges = JsonbufBridges()
        self.indent = '    '
        self.__code = CodeWriter(filename=p.join(output, '{}.cs'.format(self.schema.name)))

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
        uniques = []
        namespaces = self.__get_namespaces(self.schema.descriptor)
        self.__code.write('using System.Collections.Generic;')
        for ns in namespaces:
            if ns in uniques: continue
            uniques.append(ns)
            self.__code.write('using {};'.format(ns))
        self.__code.write('')
        count = self.schema.classes['count']  # type: int
        for n in range(count):
            cls = self.schema.classes[n]  # type: ClassDescriptor
            ns = cls.namespace if cls.namespace else 'jsonbuf.{}'.format(self.schema.name)
            self.__code.write('namespace %s\n{' % ns)
            self.__generate_class(cls, indent=self.indent)
            self.__code.write('}\n')
        self.__code.close(True)

    @staticmethod
    def __ctype(type): # type: (str)->str
        if type == JSONTYPE_int8: return 'sbyte'
        if type in (JSONTYPE_uint8, JSONTYPE_byte): return 'byte'
        if type in (JSONTYPE_short, JSONTYPE_int16): return 'short'
        if type in (JSONTYPE_ushort, JSONTYPE_uint16): return 'ushort'
        if type in (JSONTYPE_ulong, JSONTYPE_uint64): return 'ulong'
        if type in (JSONTYPE_long, JSONTYPE_int64): return 'long'
        if type in (JSONTYPE_int, JSONTYPE_int32): return 'int'
        if type in (JSONTYPE_uint, JSONTYPE_uint32): return 'uint'
        if type in (JSONTYPE_float, JSONTYPE_float32): return 'float'
        if type in (JSONTYPE_double, JSONTYPE_float64): return 'double'
        return type

    def __rtype(self, type):
        if isinstance(type, ClassDescriptor): return type.name
        if isinstance(type, ArrayDescriptor):
            if not type.mutable:
                return (self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type)) + '[]'
            return 'List<{}>'.format(self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type))
        if isinstance(type, DictionaryDescriptor):
            return 'Dictionary<{}, {}>'\
                .format(self.__ctype(type.key), self.__rtype(type=type.descriptor) if type.descriptor else self.__ctype(type.type))
        if isinstance(type, FieldDescriptor):
            if type.descriptor: return self.__rtype(type=type.descriptor)
            return self.__ctype(type.type) if not type.enum else type.enum
        assert isinstance(type, str)
        return self.__ctype(type)

    def __generate_class(self, cls, indent=''):
        self.__code.write('{}public partial class {}:IJsonbuf'.format(indent, cls.name))
        self.__code.write('{}{{'.format(indent))
        for filed in cls.fields:
            self.__code.write('{}    public {} {};'.format(indent, self.__rtype(filed), filed.name))
        self.__code.write('')
        self.__generate_encode_method(cls, indent=indent + self.indent)
        self.__code.write('')
        self.__generate_decode_method(cls, indent=indent + self.indent)
        self.__code.write('{}}}'.format(indent))
        self.__code.write('')

    def __generate_decode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        self.__code.write('{}public void Deserialize(JsonbufReader decoder)'.format(indent))
        self.__code.write('{}{{'.format(indent))
        index = IndexAttr(0)
        for field in cls.fields:
            self.__generate_decode_field(name=field.name, descriptor=field, indent=indent + self.indent, level=1, attr=index)
        self.__code.write('{}}}'.format(indent))

    def __generate_encode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        self.__code.write('{}public void Serialize(JsonbufWriter encoder)'.format(indent))
        self.__code.write('{}{{'.format(indent))
        index = IndexAttr(0)
        for field in cls.fields:
            self.__generate_encode_field(name=field.name, descriptor=field, indent=indent + self.indent, level=1, attr=index)
        self.__code.write('{}}}'.format(indent))

    @staticmethod
    def __get_decode_m(type):
        if type == JSONTYPE_bool: return 'ReadBoolean'
        elif type == JSONTYPE_int8: return 'ReadSByte'
        elif type in (JSONTYPE_uint8, JSONTYPE_byte): return 'ReadByte'
        elif type in (JSONTYPE_int16, JSONTYPE_short): return 'ReadInt16'
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort): return 'ReadUInt16'
        elif type in (JSONTYPE_int32, JSONTYPE_int): return 'ReadInt32'
        elif type in (JSONTYPE_uint32, JSONTYPE_uint): return 'ReadUInt32'
        elif type in (JSONTYPE_int64, JSONTYPE_long): return 'ReadInt64'
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong): return 'ReadUInt64'
        elif type in (JSONTYPE_float32, JSONTYPE_float): return 'ReadSingle'
        elif type in (JSONTYPE_float64, JSONTYPE_double): return 'ReadDouble'
        elif type == JSONTYPE_string: return 'ReadString'
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
            self.__code.write('{}{} = new {}();'.format(indent, name, self.__rtype(descriptor)))
            self.__code.write('{}{}.Deserialize(decoder);'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = self.__local_name(attr.next)
            count = 'c{}'.format(index)
            element = 't{}'.format(index)
            self.__code.write('{}var {} = decoder.{}();'.format(indent, count, self.__get_decode_m(JSONTYPE_uint)))
            self.__code.write('{}if ({} == 0xFFFFFFFF) {{ {} = null; }} else {{'.format(indent, count, name))
            rtype = self.__rtype(descriptor)
            sep = rtype.find('[') + 1
            constructor = '{}()'.format(rtype) if descriptor.mutable else (rtype[:sep] + count + rtype[sep:])
            self.__code.write('{}{} = new {};'.format(indent, name, constructor))
            self.__code.write('{}for (var {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            self.__code.write('%s{' % indent)
            self.__code.write('{}    {} {};'.format(indent, self.__rtype(descriptor.descriptor if descriptor.descriptor else descriptor.type), element))
            if descriptor.descriptor:
                self.__generate_decode_field(element, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}    {} = decoder.{}();'.format(indent, element, self.__get_decode_m(descriptor.type)))
            if descriptor.mutable:
                self.__code.write('{}    {}.Add({});'.format(indent, name, element))
            else:
                self.__code.write('{}    {}[{}] = {};'.format(indent, name, index, element))
            self.__code.write('%s}}' % indent)
        elif isinstance(descriptor, DictionaryDescriptor):
            index = self.__local_name(attr.next)
            count = 'c{}'.format(index)
            key = 'k{}'.format(index)
            val = 'v{}'.format(index)
            self.__code.write('{}var {} = decoder.{}();'.format(indent, count, self.__get_decode_m(JSONTYPE_uint)))
            self.__code.write('{}if ({} == 0xFFFFFFFF) {{ {} = null; }} else {{'.format(indent, count, name))
            self.__code.write('{}{} = new {}();'.format(indent, name, self.__rtype(descriptor)))
            self.__code.write('{}for (var {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            self.__code.write('%s{' % indent)
            self.__code.write('{}    {} {};'.format(indent, self.__rtype(descriptor.descriptor if descriptor.descriptor else descriptor.type), val))
            self.__code.write('{}    var {} = decoder.{}();'.format(indent, key, self.__get_decode_m(descriptor.key)))
            if descriptor.descriptor:
                self.__generate_decode_field(val, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}    {} = decoder.{}();'.format(indent, val, self.__get_decode_m(descriptor.type)))
            self.__code.write('{}    {}[{}] = {};'.format(indent, name, key, val))
            self.__code.write('%s}}' % indent)
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.__generate_decode_field(name=field.name, descriptor=field.descriptor, indent=indent, level=level, attr=attr)
            else:
                if field.enum:
                    self.__code.write('{}{} = ({})decoder.{}();'.format(indent, name, field.enum, self.__get_decode_m(field.type)))
                else:
                    self.__code.write('{}{} = decoder.{}();'.format(indent, name, self.__get_decode_m(field.type)))

    def __generate_encode_field(self, name, descriptor, indent, level=0, attr=None): # type: (str, Descriptor, str, int, IndexAttr)->None
        if isinstance(descriptor, ClassDescriptor):
            self.__code.write('{}{}.Serialize(encoder);'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = self.__local_name(attr.next)
            count = ('{}.Count' if descriptor.mutable else '{}.Length').format(name)
            element = 't{}'.format(index)
            self.__code.write('{}if ({} == null) {{ encoder.Write((int)-1); }} else {{'.format(indent, name))
            self.__code.write('{}encoder.Write((uint){});'.format(indent, count))
            self.__code.write('{}for (var {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            self.__code.write('%s{' % indent)
            self.__code.write('{}    var {} = {}[{}];'.format(indent, element, name, index))
            if descriptor.descriptor:
                self.__generate_encode_field(element, descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}    encoder.Write({});'.format(indent, element))
            self.__code.write('%s}}' % indent)
        elif isinstance(descriptor, DictionaryDescriptor):
            index = self.__local_name(attr.next)
            count = '{}.Count'.format(name)
            pair = 'p{}'.format(index)
            self.__code.write('{}if ({} == null) {{ encoder.Write((int)-1); }} else {{'.format(indent, name))
            self.__code.write('{}encoder.Write((uint){});'.format(indent, count))
            self.__code.write('{}foreach (var {} in {})'.format(indent, pair, name))
            self.__code.write('%s{' % indent)
            self.__code.write('{}    encoder.Write({}.Key);'.format(indent, pair))
            if descriptor.descriptor:
                self.__generate_encode_field('{}.Value'.format(pair), descriptor=descriptor.descriptor, indent=indent + self.indent, level=level + 1, attr=attr)
            else:
                self.__code.write('{}    encoder.Write({}.Value);'.format(indent, pair))
            self.__code.write('%s}}' % indent)
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.__generate_encode_field(name=field.name, descriptor=field.descriptor, indent=indent, level=level, attr=attr)
            else:
                if field.enum:
                    self.__code.write('{}encoder.Write(({}){});'.format(indent, self.__rtype(field.type), field.name))
                else:
                    self.__code.write('{}encoder.Write({});'.format(indent, field.name))


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
        generator = CSharpGenerator(schema, output)
        generator.generate()
        print('>>> {}\n'.format(p.abspath(generator.filename)))

if __name__ == '__main__':
    main()
