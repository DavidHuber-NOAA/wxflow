import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Union

import yaml

from .attrdict import AttrDict
from .jinja import Jinja

__all__ = ['YAMLFile', 'parse_yaml', 'parse_j2yaml',
           'save_as_yaml', 'dump_as_yaml', 'vanilla_yaml']


class YAMLFile(AttrDict):
    """
    Reads a YAML file as an AttrDict and recursively converts
    nested dictionaries into AttrDict.
    This is the entry point for all YAML files.
    """

    def __init__(self, path=None, data=None):
        super().__init__()

        if path and data:
            print("Ignoring 'data' and using 'path' argument")

        config = None
        if path is not None:
            config = parse_yaml(path=path)
        elif data is not None:
            config = parse_yaml(data=data)

        if config is not None:
            self.update(config)

    def save(self, target):
        save_as_yaml(self, target)

    @property
    def dump(self):
        return dump_as_yaml(self)

    @property
    def as_dict(self):
        return vanilla_yaml(self)


def save_as_yaml(data, target):
    # specifies a wide file so that long strings are on one line.
    with open(target, 'w') as fh:
        yaml.safe_dump(vanilla_yaml(data), fh,
                       width=100000, sort_keys=False)


def dump_as_yaml(data):
    return yaml.dump(vanilla_yaml(data), sys.stdout, encoding='utf-8',
                     width=100000, sort_keys=False)


def parse_yaml(path=None, data=None,
               encoding='utf-8', loader=yaml.SafeLoader):
    """
    Load a yaml configuration file and resolve any environment variables
    The environment variables must have !ENV before them and be in this format
    to be parsed: ${VAR_NAME}.
    E.g.:
    database:
        host: !ENV ${HOST}
        port: !ENV ${PORT}
    app:
        log_path: !ENV '/var/${LOG_PATH}'
        something_else: !ENV '${AWESOME_ENV_VAR}/var/${A_SECOND_AWESOME_VAR}'
    :param str path: the path to the yaml file
    :param str data: the yaml data itself as a stream
    :param Type[yaml.loader] loader: Specify which loader to use. Defaults to yaml.SafeLoader
    :param str encoding: the encoding of the data if a path is specified, defaults to utf-8
    :return: the dict configuration
    :rtype: Dict[str, Any]

    Adopted from:
    https://dev.to/mkaranasou/python-yaml-configuration-with-environment-variables-parsing-2ha6
    """
    # define tags
    envtag = '!ENV'
    inctag = '!INC'
    # pattern for global vars: look for ${word}
    pattern = re.compile(r'.*?\${(\w+)}.*?')
    loader = loader or yaml.SafeLoader

    # the envtag will be used to mark where to start searching for the pattern
    # e.g. somekey: !ENV somestring${MYENVVAR}blah blah blah
    loader.add_implicit_resolver(envtag, pattern, None)
    loader.add_implicit_resolver(inctag, pattern, None)

    def expand_env_variables(line):
        match = pattern.findall(line)  # to find all env variables in line
        if match:
            full_value = line
            for g in match:
                full_value = full_value.replace(
                    f'${{{g}}}', os.environ.get(g, f'${{{g}}}')
                )
            return full_value
        return line

    def constructor_env_variables(loader, node):
        """
        Extracts the environment variable from the node's value
        :param yaml.Loader loader: the yaml loader
        :param node: the current node in the yaml
        :return: the parsed string that contains the value of the environment
        variable
        """
        value = loader.construct_scalar(node)
        return expand_env_variables(value)

    def constructor_include_variables(loader, node):
        """
        Extracts the environment variable from the node's value
        :param yaml.Loader loader: the yaml loader
        :param node: the current node in the yaml
        :return: the content of the file to be included
        """
        value = loader.construct_scalar(node)
        value = expand_env_variables(value)
        expanded = parse_yaml(value)
        return expanded

    loader.add_constructor(envtag, constructor_env_variables)
    loader.add_constructor(inctag, constructor_include_variables)

    if path:
        with open(path, 'r', encoding=encoding) as conf_data:
            return yaml.load(conf_data, Loader=loader)
    elif data:
        return yaml.load(data, Loader=loader)
    else:
        raise ValueError(
            "Either a path or data should be defined as input")


def vanilla_yaml(ctx):
    """
    Transform an input object of complex type as a plain type
    """
    if isinstance(ctx, AttrDict):
        return {kk: vanilla_yaml(vv) for kk, vv in ctx.items()}
    elif isinstance(ctx, list):
        return [vanilla_yaml(vv) for vv in ctx]
    elif isinstance(ctx, datetime.datetime):
        return ctx.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return ctx


def parse_j2yaml(path: str, data: Dict, searchpath: Union[str, List] = '/', allow_missing: bool = True) -> Dict[str, Any]:
    """
    Description
    -----------
    Load a compound jinja2-templated yaml file and resolve any templated variables.
    The jinja2 templates are first resolved and then the rendered template is parsed as a yaml.

    Parameters
    ----------
    path : str
        the path to the jinja2 templated yaml file
    data : Dict[str, Any], optional
        the context for jinja2 templating
    searchpath: str | List
        additional search paths for included jinja2 templates
    allow_missing: bool
        whether to allow missing variables in a jinja2 template or not
    Returns
    -------
    Dict[str, Any]
        the dict configuration
    """

    if not os.path.exists(path):
        raise FileNotFoundError(f"Input j2yaml file {path} does not exist!")

    return YAMLFile(data=Jinja(path, data, searchpath=searchpath, allow_missing=allow_missing).render)
