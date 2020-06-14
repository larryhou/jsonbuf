#!/usr/bin/env python3
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

class Descriptor(object):
    def __init__(self):
        self.tag = ''

    def validate(self):
        pass

class FieldDescriptor(Descriptor):
    def __init__(self):
        super(FieldDescriptor, self).__init__()
        self.tag = 'field'
        self.name = ''
        self.type = ''
        self.descriptor = None # type: Descriptor

    def validate(self):
        assert self.type in ('int', 'uint', 'float', 'double', 'string', 'bool', 'array', 'class')
        if self.type == 'class':
            assert self.descriptor and isinstance(self.descriptor, ClassDescriptor)
            self.descriptor.validate()

class ArrayDescriptor(Descriptor):
    def __init__(self):
        super(ArrayDescriptor, self).__init__()
        self.tag = 'array'
        self.type = ''
        self.descriptor = None # type: ClassDescriptor

class ClassDescriptor(Descriptor):
    def __init__(self):
        super(ClassDescriptor, self).__init__()
        self.tag = 'class'
        self.name = ''
        self.fields = [] # type: list[FieldDescriptor]

    def validate(self):
        for field in self.fields: field.validate()

class JsonbufSchema(object):
    def __init__(self):
        self.descriptor = None # type: Descriptor
        self.classes = [] # type: list[ClassDescriptor]

    def check_type(self, type):
        assert 'JSONTYPE_{}'.format(type) in globals(), 'JSONTYPE_{}'.format(type)

    def load(self, filename):
        schema = etree.parse(filename).getroot()
        self.descriptor, self.classes = self.decode(schema)
        return self.descriptor

    def dump(self, filename):
        schema = self.encode(descriptor=self.descriptor)
        with open(filename, 'w') as fp:
            content = etree.tostring(schema, pretty_print=True, encoding='utf-8').__decode('utf-8')
            fp.write(content)
            print('>>> {}'.format(p.abspath(fp.name)))
            print(content)

    def encode(self, descriptor):
        schema = etree.Element(descriptor.tag)
        if isinstance(descriptor, ArrayDescriptor):
            schema.set('type', descriptor.type)
            if descriptor.type == 'class':
                assert isinstance(descriptor.descriptor, ClassDescriptor)
                schema.append(self.encode(descriptor.descriptor))
            elif descriptor.type == 'array':
                assert isinstance(descriptor.descriptor, ArrayDescriptor)
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
            else:
                self.check_type(descriptor.type)
        else:
            raise NotImplementedError('<{}/>'.format(descriptor.tag))
        return schema

    def decode(self, schema):
        classes = []
        tag = schema.tag
        if tag == 'array':
            array = ArrayDescriptor()
            array.type = schema.get('type')
            if array.type == 'class':
                class_schema = schema[0]
                assert class_schema.tag == 'class'
                array.descriptor, subclasses = self.decode(schema=class_schema)
                if subclasses: classes.extend(subclasses)
            elif array.type == 'array':
                array_schema = schema[0]
                assert array_schema.tag == 'array'
                array.descriptor, subclasses = self.decode(schema=array_schema)
                if subclasses: classes.extend(subclasses)
            else:
                self.check_type(array.type)
            return array, classes
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
            if field.type == 'class':
                class_schema = schema[0]
                assert class_schema.tag == 'class'
                field.descriptor, subclasses = self.decode(schema=class_schema)
                if subclasses: classes.extend(subclasses)
            elif field.type == 'array':
                array_schema = schema[0]
                assert array_schema.tag == 'array'
                field.descriptor, subclasses = self.decode(schema=array_schema)
                if subclasses: classes.extend(subclasses)
            else:
                self.check_type(field.type)
            return field, classes
        else:
            raise NotImplementedError('<{}/> not supported'.format(tag))

class JsonbufSerializer(object):
    def __init__(self, schema):
        self.schema = schema # type: Descriptor
        self.context = None

    def load(self, filename):
        self.context = json.load(fp=open(filename, 'r'))

    def serialize(self, fp): # type: (io.BytesIO)->None
        self.__encode(self.schema, value=self.context, buffer=fp)

    def deserilize(self, fp): # type: (io.BytesIO)->any
        self.context = self.__decode(self.schema, buffer=fp)
        return self.context

    def __encode_null(self, buffer):
        self.__encode_v(-1, type=JSONTYPE_int32, buffer=buffer)

    def __decode_null(self, buffer): # type: (io.BytesIO)->bool
        if self.__decode_v(type=JSONTYPE_int32, buffer=buffer) == -1: return True
        buffer.seek(-4, os.SEEK_CUR)
        return False

    def __encode_v(self, value, type, buffer): # type: (any, str, io.BytesIO)->None
        if type == JSONTYPE_bool:
            buffer.write(struct.pack('b', 1 if value else 0))
        elif type == JSONTYPE_int8:
            buffer.write(struct.pack('b', value))
        elif type == JSONTYPE_uint8:
            buffer.write(struct.pack('B', value))
        elif type in (JSONTYPE_int16, JSONTYPE_short):
            buffer.write(struct.pack('>h', value))
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort):
            buffer.write(struct.pack('>H', value))
        elif type in (JSONTYPE_int32, JSONTYPE_int):
            buffer.write(struct.pack('>i', value))
        elif type in (JSONTYPE_uint32, JSONTYPE_uint):
            buffer.write(struct.pack('>I', value))
        elif type in (JSONTYPE_int64, JSONTYPE_long):
            buffer.write(struct.pack('>q', value))
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong):
            buffer.write(struct.pack('>Q', value))
        elif type in (JSONTYPE_float32, JSONTYPE_float):
            buffer.write(struct.pack('>f', value))
        elif type in (JSONTYPE_float64, JSONTYPE_double):
            buffer.write(struct.pack('>d', value))
        elif type == JSONTYPE_string:
            if not value:
                if value is None:
                    self.__encode_null(buffer)
                else:
                    buffer.write(struct.pack('>I', 0))
            else:
                value = str(value)
                bin = value.encode('utf-8')
                buffer.write(struct.pack('>I', len(bin)))
                buffer.write(bin)
        else:
            raise NotImplementedError('Not support for encoding value[={}] with {!r} type'.format(value, type))

    def __decode_v(self, type, buffer): # type: (str, io.BytesIO)->any
        if type == JSONTYPE_bool:
            v, = struct.unpack('b', buffer.read(1))
            v = v != 0
        elif type == JSONTYPE_int8:
            v, = struct.unpack('b', buffer.read(1))
        elif type == JSONTYPE_uint8:
            v, = struct.unpack('B', buffer.read(1))
        elif type in (JSONTYPE_int16, JSONTYPE_short):
            v, = struct.unpack('>h', buffer.read(2))
        elif type in (JSONTYPE_uint16, JSONTYPE_ushort):
            v, = struct.unpack('>H', buffer.read(2))
        elif type in (JSONTYPE_int32, JSONTYPE_int):
            v, = struct.unpack('>i', buffer.read(4))
        elif type in (JSONTYPE_uint32, JSONTYPE_uint):
            v, = struct.unpack('>I', buffer.read(4))
        elif type in (JSONTYPE_int64, JSONTYPE_long):
            v, = struct.unpack('>q', buffer.read(8))
        elif type in (JSONTYPE_uint64, JSONTYPE_ulong):
            v, = struct.unpack('>Q', buffer.read(8))
        elif type in (JSONTYPE_float32, JSONTYPE_float):
            v, = struct.unpack('>f', buffer.read(4))
        elif type in (JSONTYPE_float64, JSONTYPE_double):
            v, = struct.unpack('>d', buffer.read(8))
        elif type == JSONTYPE_string:
            size, = struct.unpack('>I', buffer.read(4))
            if size == 0xFFFFFFFF: v = None
            else:
                v = buffer.read(size).decode('utf-8') if size > 0 else ''
        else:
            raise NotImplementedError('Not support for encoding value[={}] with {!r} type'.format(value, type))
        return v

    def __encode(self, schema, value, buffer): # type: (Descriptor, any, io.BytesIO)->None
        if isinstance(schema, ArrayDescriptor):
            if not value:
                self.__encode_null(buffer)
                return
            assert schema.descriptor and isinstance(value, list)
            self.__encode_v(len(value), type=JSONTYPE_uint32, buffer=buffer)
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor)
                for element in value:
                    self.__encode(schema.descriptor, value=element, buffer=buffer)
            else:
                for element in value:
                    self.__encode_v(element, type=schema.type, buffer=buffer)
        elif isinstance(schema, ClassDescriptor):
            if not value:
                self.__encode_null(buffer)
                return
            assert schema.fields and isinstance(value, dict), (schema, value)
            for field in schema.fields:
                self.__encode(field, value=value.get(field.name), buffer=buffer)
        elif isinstance(schema, FieldDescriptor):
            if schema.type == 'class':
                assert isinstance(schema.descriptor, ClassDescriptor)
                self.__encode(schema.descriptor, value=value, buffer=buffer)
            elif schema.type == 'array':
                assert isinstance(schema.descriptor, ArrayDescriptor)
                self.__encode(schema.descriptor, value=value, buffer=buffer)
            else:
                self.__encode_v(value, type=schema.type, buffer=buffer)

    def __decode(self, schema, buffer):
        if isinstance(schema, ArrayDescriptor):
            if self.__decode_null(buffer): return None
            elements = []
            size = self.__decode_v(JSONTYPE_uint32, buffer=buffer)
            if schema.descriptor:
                assert isinstance(schema.descriptor, ClassDescriptor) \
                       or isinstance(schema.descriptor, ArrayDescriptor)
                for _ in range(size):
                    elements.append(self.__decode(schema.descriptor, buffer=buffer))
            else:
                for _ in range(size):
                    elements.append(self.__decode_v(schema.type, buffer=buffer))
            return elements
        elif isinstance(schema, ClassDescriptor):
            if self.__decode_null(buffer): return None
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
            else:
                return self.__decode_v(schema.type, buffer=buffer)

def main():
    import argparse,sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--file', '-f', required=True)
    arguments.add_argument('--schema', '-s', required=True)
    options = arguments.parse_args(sys.argv[1:])

    schema = JsonbufSchema()
    descriptor = schema.load(filename=options.schema)
    serializer = JsonbufSerializer(schema=descriptor)
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

