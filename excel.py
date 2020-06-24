#!/usr/bin/env python
# encoding: utf-8
from __future__ import print_function
import os.path as p
import os, re, xlrd
import lxml.etree as etree

from jsonbuf import *

class XLSField(object):
    def __init__(self):
        self.column = -1
        self.name = ''
        self.type = ''
        self.primary = False
        self.descriptor = None # type: XLSClass
        self.separator = ''

class XLSClass(object):
    def __init__(self):
        self.name = ''
        self.fields = [] # type: list[XLSField]

    def schema(self):
        type = etree.Element('class')
        type.set('name', self.name)
        class_map = {}
        for field in self.fields:
            item = etree.Element('field')
            item.set('name', field.name)
            if field.separator:
                item.set('type', 'array')
                array = etree.Element('array')
                array.set('type', field.type)
                item.append(array)
            elif field.descriptor:
                if field.descriptor.name in class_map:
                    cls = etree.Element('class')
                    cls.set('name', field.descriptor.name)
                    item.append(cls)
                else:
                    item.append(field.descriptor.schema())
                    class_map[field.descriptor.name] = True
            else:
                item.set('type', field.type)
            type.append(item)
        return type


class Commands(object):
    serialize = 'serialize'
    deserialize = 'deserialize'
    schema = 'schema'

    @classmethod
    def get_choices(cls):
        choices = []
        for k, v in vars(cls).items():
            if k == v: choices.append(v)
        return choices

def collect(dirname, pattern):
    result = []
    for basepath, _, names in os.walk(dirname):
        for filename in names:
            if not filename.startswith('~') and pattern.search(filename):
                result.append(p.join(basepath, filename))
    return result


def main():
    import argparse, sys
    arguments = argparse.ArgumentParser()
    arguments.add_argument('--command', '-c', choices=Commands.get_choices(), default=Commands.serialize)
    arguments.add_argument('--file', '-f', nargs='+')
    arguments.add_argument('--path', '-p', nargs='+')
    arguments.add_argument('--output', '-o', default='.')
    options = arguments.parse_args(sys.argv[1:])

    script_path = p.dirname(p.abspath(__file__))

    output = p.abspath(options.output)
    if not p.exists(output): os.makedirs(output)

    command = options.command # type: str
    if command == Commands.serialize:
        pass
    elif command == Commands.deserialize:
        pass
    elif command == Commands.schema:
        pattern = re.compile(r'\.xlsx?$')
        exclude = re.compile(r'/ServerOnly/')
        excels = []
        if options.path:
            for dirname in options.path:
                excels.extend(collect(dirname, pattern))
        if options.file:
            for filename in options.file:
                if p.exists(filename) and pattern.search(filename):
                    excels.append(filename)
        assert excels
        for filename in excels:
            if exclude.search(filename): continue
            print('[x] {}'.format(p.abspath(filename)))
            name = re.sub(r'\.[^.]+$', '', p.basename(filename))
            type = XLSClass()
            type.name = name + 'Config'
            class_map = {}
            sheet = xlrd.open_workbook(filename).sheet_by_index(0)
            for c in range(sheet.ncols):
                cell = sheet.cell(0, c)
                if cell.ctype != xlrd.XL_CELL_TEXT: continue
                components = re.split(r'\s*:\s*', cell.value.strip())
                fsize = len(components)
                if fsize == 1: continue
                field_name = components[0]
                field = XLSField()
                field.primary = field_name.startswith('#')
                field.name = re.sub(r'#', '', field_name)
                if fsize == 2:
                    field_type = components[1]
                    if field_type.startswith('vector'):
                        if field_type not in class_map:
                            vector = XLSClass()
                            vector.name = field_type.title()
                            for x in range(int(field_type[-1])):
                                f = XLSField()
                                f.type = JSONTYPE_float
                                f.name = chr(ord('x') + x)
                                vector.fields.append(f)
                        else:
                            vector = class_map[field_type]
                        field.type = 'class'
                        field.descriptor = vector
                    else:
                        field.type = field_type
                    type.fields.append(field)
                elif len(components) == 3:
                    field = XLSField()
                    field.name, field.type, field.separator = components
                    type.fields.append(field)
                else:
                    print(repr(cell.value), components)
                    continue
            assert type.fields
            table = etree.Element('class')
            table.set('name', '{}Table'.format(name))
            records = etree.Element('array')
            records.set('type', 'class')
            records.append(type.schema())
            table.append(records)

            excel_schema_path = p.join(script_path, 'schemas/excel')
            if not p.exists(excel_schema_path): os.makedirs(excel_schema_path)
            with open(p.join(excel_schema_path, '{}Conf.xml'.format(name)), 'w+') as fp:
                fp.write(etree.tostring(table, pretty_print=True))
                fp.seek(0)
                print('>>> {}'.format(fp.name))
                print(fp.read())
                print()



if __name__ == '__main__':
    main()
