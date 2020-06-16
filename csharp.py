#!/usr/bin/env python
# encoding: utf-8

from __future__ import print_function
from jsonbuf import *


class CSharpGenerator(object):
    def __init__(self, schema):
        self.schema = schema  # type: JsonbufSchema

    def generate(self):
        for name, cls in self.schema.classes.items():
            self.generate_class(cls)

    def ctype(self, type): # type: (str)->str
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
            if type.descriptor:
                return self.rtype(type=type.descriptor)
            return self.ctype(type.type) if not type.enum else type.enum
        assert isinstance(type, str)
        return self.ctype(type)

    def generate_class(self, cls):
        print('public class {}'.format(cls.name))
        for filed in cls.fields:
            print('    public {} {};'.format(self.rtype(filed), filed.name))
        print()


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
