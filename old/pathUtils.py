import os
import json
from maya import cmds
import re


def conform_path(path):
    return join_path(*split_path(path.replace('\\', '/')))


def join_path(*args):
    path = list()
    for arg in args:
        parts = split_path(arg)
        for part in parts:
            part = str(part)
            if part:
                path.append(part)
    return '/'.join(path)


def split_path(path):
    conformed_path = path.replace('\\', '/')
    list_ = list()
    for item in conformed_path.split('/'):
        if item:
            list_.append(item)
    return list_


def decompose_file_path(path):
    path_split = split_path(path)

    file_name = path_split.pop()
    location = join_path(*path_split)
    return location, file_name


class JsonFile(object):
    default_location = cmds.internalVar(userPrefDir=True)
    extension = 'json'

    def __init__(self, name):
        if not self.is_one(name):
            cmds.error('\'{}\' is not a valid argument for \'{}\' class.'.format(name, self.__class__.__name__))
        self.name = str(name)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.name == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __iter__(self):
        return iter(self.name)

    def endswith(self, item):
        return self.name.endswith(item)

    def startswith(self, item):
        return self.name.startswith(item)

    @classmethod
    def compress_data(cls, data):
        return data

    @classmethod
    def uncompress_data(cls, data):
        return data

    @classmethod
    def format_file_name(cls, file_name):
        file_name = str(file_name)
        if not file_name.lower().endswith('.{0}'.format(cls.extension)):
            return '{0}.{1}'.format(file_name, cls.extension)
        return file_name

    @classmethod
    def create(cls, *args, **kwargs):
        pass

    @classmethod
    def create_file(cls, data, location=None, file_name=None, force=False):
        location = cls.default_location if location is None else str(location)
        file_name = cls.get_default_file_name() if file_name is None else str(file_name)
        force = bool(force)

        location = conform_path(location)
        file_name = cls.format_file_name(file_name)
        path = join_path(location, file_name)

        if not os.path.isdir(location):
            raise cmds.error('The given location is invalid -> \'{}\''.format(location))
        if not force and os.path.isfile(path):
            raise cmds.error('The given path already exists -> \'{}\''.format(path))

        with open(path, 'w') as f:
            json.dump(None, f)
        json_file = cls(path)
        json_file.write(data)

        print('The file \'{0}\' has been created.'.format(json_file.get_path()))
        return json_file

    @classmethod
    def get_default_file_name(cls):
        file_name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        return '{0}.{1}'.format(file_name, cls.extension)

    @classmethod
    def get(cls, location=None, file_name=None):
        location = cls.default_location if location is None else str(location)
        file_name = cls.get_default_file_name() if file_name is None else cls.format_file_name(file_name)

        full_path = join_path(location, file_name)
        if cls.is_one(full_path):
            return cls(full_path)

        print('The file \'{0}\' does not exist.'.format(full_path))
        return None

    def load(self, *args, **kwargs):
        print('The file \'{0}\' has been loaded.'.format(self.get_path()))

    @classmethod
    def is_one(cls, path):
        path = str(path)
        if os.path.isfile(path):
            if path.lower().endswith(cls.extension):
                return True
        return False

    def write(self, data):
        data = self.compress_data(data)
        with open(self.get_path(), 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def get_path(self):
        return self.name

    def read(self):
        with open(self.get_path(), 'r') as f:
            data = json.load(f)
        return self.uncompress_data(data)

    def get_file_name(self, extension=True):
        name = self.get_path().split('/')[-1]
        if extension:
            return name
        return name.split('.')[0]

    def delete(self):
        os.remove(self.get_path())
        print('The file \'{0}\' has been deleted.'.format(self.get_path()))
