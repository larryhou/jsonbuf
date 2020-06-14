#!/usr/bin/env python3
import lxml.etree as etree
import os.path as p

TYPE_double = 'double'
TYPE_float = 'float'
TYPE_ushort = 'ushort'
TYPE_short = 'short'
TYPE_uint = 'uint'
TYPE_int = 'int'

TYPE_int8 = 'int8'
TYPE_int16 = 'int16'
TYPE_int32 = 'int32'
TYPE_int64 = 'int64'
TYPE_uint8 = 'uint8'
TYPE_uint16 = 'uint16'
TYPE_uint32 = 'uint32'
TYPE_uint64 = 'uint64'
TYPE_float32 = 'float32'
TYPE_float64 = 'float64'
TYPE_string = 'string'
TYPE_bool = 'bool'

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
        assert 'TYPE_{}'.format(type) in globals(), 'TYPE_{}'.format(type)

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
    def __init__(self):
        pass


def main():
    import argparse,sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--file', '-f', required=True)
    options = arguments.parse_args(sys.argv[1:])

    schema = JsonbufSchema()
    descriptor = schema.load(filename=options.file)
    array = descriptor.descriptor # type: ArrayDescriptor
    print(vars(descriptor))
    print(vars(array.descriptor))
    print([[x.name for x in c.fields] for c in schema.classes])

    schema.dump(filename='test.xml')


if __name__ == '__main__':
    main()

