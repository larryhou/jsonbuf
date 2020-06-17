#!/usr/bin/env python
# encoding: utf-8

from __future__ import print_function
from jsonbuf import *


class CSharpGenerator(object):
    def __init__(self, schema):
        self.schema = schema  # type: JsonbufSchema
        self.indent = '    '

    def generate(self):
        print('namespace jsonbuf\n{')
        for name, cls in self.schema.classes.items():
            subindent = self.indent
            if cls.namespace:
                subindent += self.indent
                print('{}namespace {}'.format(self.indent, cls.namespace))
                print('%s{' % self.indent)
            self.generate_class(cls, indent=subindent)
            if cls.namespace: print('%s}' % self.indent)
        print('}')

    @staticmethod
    def ctype(type): # type: (str)->str
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

    def rtype(self, type):
        if isinstance(type, ClassDescriptor): return type.name
        if isinstance(type, ArrayDescriptor):
            if not type.mutable:
                return (self.rtype(type=type.descriptor) if type.descriptor else self.ctype(type.type)) + '[]'
            return 'List<{}>'.format(self.rtype(type=type.descriptor) if type.descriptor else self.ctype(type.type))
        if isinstance(type, DictionaryDescriptor):
            return 'Dictionary<{}, {}>'\
                .format(type.key, self.rtype(type=type.descriptor) if type.descriptor else self.ctype(type.type))
        if isinstance(type, FieldDescriptor):
            if type.descriptor: return self.rtype(type=type.descriptor)
            return self.ctype(type.type) if not type.enum else type.enum
        assert isinstance(type, str)
        return self.ctype(type)

    def generate_class(self, cls, indent=''):
        print('{}public class {}'.format(indent, cls.name))
        print('{}{{'.format(indent))
        for filed in cls.fields:
            print('{}    public {} {};'.format(indent, self.rtype(filed), filed.name))
        print('')
        self.generate_encode_method(cls, indent=indent+self.indent)
        print('')
        self.generate_decode_method(cls, indent=indent+self.indent)
        print('{}}}'.format(indent))
        print('')

    def generate_decode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        print('{}public void Deserialize(JsonbufReader decoder)'.format(indent))
        print('{}{{'.format(indent))
        index = 0
        for field in cls.fields:
            self.generate_decode_field(name=field.name, descriptor=field, indent=indent+self.indent, level=1, order=index)
            index += 1
        print('{}}}'.format(indent))

    def generate_encode_method(self, cls, indent): # type: (ClassDescriptor, str)->None
        print('{}public void Serialize(JsonbufWriter encoder)'.format(indent))
        print('{}{{'.format(indent))
        index = 0
        for field in cls.fields:
            self.generate_encode_field(name=field.name, descriptor=field, indent=indent+self.indent, level=1, order=index)
            index += 1
        print('{}}}'.format(indent))

    @staticmethod
    def get_decode_m(type):
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

    def generate_decode_field(self, name, descriptor, indent, level=0, order=0): # type: (str, Descriptor, str, int, int)->None
        if isinstance(descriptor, ClassDescriptor):
            print('{}{} = new {}();'.format(indent, name, self.rtype(descriptor)))
            print('{}{}.Deserialize(decoder);'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = chr(108 + level)
            count = 'c{}'.format(chr(ord(index) + order))
            element = 'i{}'.format(index)
            print('{}var {} = decoder.{}();'.format(indent, count, self.get_decode_m(JSONTYPE_uint)))
            print('{}if ({} == 0xFFFFFFFF) {{ {} = null; }} else {{'.format(indent, count, name))
            atype = self.rtype(descriptor)
            constructor = '{}()'.format(atype) if descriptor.mutable else (atype[:-1] + count + ']')
            print('{}{} = new {};'.format(indent, name, constructor))
            print('{}for (var {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            print('%s{' % indent)
            print('{}    {} {};'.format(indent, self.rtype(descriptor.descriptor if descriptor.descriptor else descriptor.type), element))
            if descriptor.descriptor:
                self.generate_decode_field(element, descriptor=descriptor.descriptor, indent=indent+self.indent, level=level + 1, order=order)
            else:
                print('{}    {} = decoder.{}();'.format(indent, element, self.get_decode_m(descriptor.type)))
            if descriptor.mutable:
                print('{}    {}.Add({});'.format(indent, name, element))
            else:
                print('{}    {}[{}] = {};'.format(indent, name, index, element))
            print('%s}}' % indent)
        elif isinstance(descriptor, DictionaryDescriptor):
            index = chr(108 + level)
            count = 'c{}'.format(chr(ord(index) + order))
            key = 'k{}'.format(index)
            val = 'v{}'.format(index)
            print('{}var {} = decoder.{}();'.format(indent, count, self.get_decode_m(JSONTYPE_uint)))
            print('{}if ({} == 0xFFFFFFFF) {{ {} = null; }} else {{'.format(indent, count, name))
            print('{}{} = new {}();'.format(indent, name, self.rtype(descriptor)))
            print('{}for (var {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            print('%s{' % indent)
            print('{}    {} {};'.format(indent, self.rtype(descriptor.descriptor if descriptor.descriptor else descriptor.type), val))
            print('{}    var {} = decoder.{}();'.format(indent, key, self.get_decode_m(descriptor.key)))
            if descriptor.descriptor:
                self.generate_decode_field(val, descriptor=descriptor.descriptor, indent=indent+self.indent, level=level + 1, order=order)
            else:
                print('{}    {} = decoder.{}();'.format(indent, val, self.get_decode_m(descriptor.type)))
            print('{}    {}[{}] = {};'.format(indent, name, key, val))
            print('%s}}' % indent)
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.generate_decode_field(name=field.name, descriptor=field.descriptor, indent=indent, level=level, order=order)
            else:
                if field.enum:
                    print('{}{} = ({})decoder.{}();'.format(indent, name, field.enum, self.get_decode_m(field.type)))
                else:
                    print('{}{} = decoder.{}();'.format(indent, name, self.get_decode_m(field.type)))

    def generate_encode_field(self, name, descriptor, indent, level=0, order=0): # type: (str, Descriptor, str, int, int)->None
        if isinstance(descriptor, ClassDescriptor):
            print('{}{}.Serialize(encoder);'.format(indent, name))
        elif isinstance(descriptor, ArrayDescriptor):
            index = chr(108 + level)
            count = ('{}.Count' if descriptor.mutable else '{}.Length').format(name)
            element = 'i{}'.format(index)
            print('{}if ({} == null) {{ encoder.Write((int)-1); }} else {{'.format(indent, name))
            print('{}encoder.Write((uint){});'.format(indent, count))
            print('{}for (var {} = 0; {} < {}; {}++)'.format(indent, index, index, count, index))
            print('%s{' % indent)
            print('{}    var {} = {}[{}];'.format(indent, element, name, index))
            if descriptor.descriptor:
                self.generate_encode_field(element, descriptor=descriptor.descriptor, indent=indent+self.indent, level=level + 1, order=order)
            else:
                print('{}    encoder.Write({});'.format(indent, element))
            print('%s}}' % indent)
        elif isinstance(descriptor, DictionaryDescriptor):
            index = chr(108 + level)
            count = '{}.Count'.format(name)
            pair = 'p{}'.format(index)
            print('{}if ({} == null) {{ encoder.Write((int)-1); }} else {{'.format(indent, name))
            print('{}encoder.Write((uint){});'.format(indent, count))
            print('{}foreach (var {} in {})'.format(indent, pair, name))
            print('%s{' % indent)
            print('{}    encoder.Write({}.Key);'.format(indent, pair))
            if descriptor.descriptor:
                self.generate_encode_field('{}.Value'.format(pair), descriptor=descriptor.descriptor, indent=indent+self.indent, level=level + 1, order=order)
            else:
                print('{}    encoder.Write({}.Value);'.format(indent, pair))
            print('%s}}' % indent)
        else:
            assert isinstance(descriptor, FieldDescriptor)
            field = descriptor
            if field.descriptor:
                self.generate_encode_field(name=field.name, descriptor=field.descriptor, indent=indent, level=level, order=order)
            else:
                if field.enum:
                    print('{}encoder.Write(({}){});'.format(indent, self.rtype(field.type), field.name))
                else:
                    print('{}encoder.Write({});'.format(indent, field.name))



def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--schema', '-s', required=True, help='data structure definition')
    arguments.add_argument('--output', '-o', default='.', help='path for saving generated files')
    arguments.add_argument('--verbose', '-v', action='store_true', help='enable verbose printing')
    options = arguments.parse_args(sys.argv[1:])

    output = p.abspath(options.output)
    if not p.exists(output): os.makedirs(output)

    filename = p.basename(options.schema)  # type: str
    name = re.sub(r'\.[^.]+$', '', filename)

    schema = JsonbufSchema()
    schema.load(filename=options.schema)
    csharp = CSharpGenerator(schema)
    csharp.generate()


if __name__ == '__main__':
    main()
