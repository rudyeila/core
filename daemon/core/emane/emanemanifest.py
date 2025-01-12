import logging

from core.config import Configuration
from core.emulator.enumerations import ConfigDataTypes

manifest = None
try:
    from emane.shell import manifest
except ImportError:
    try:
        from emanesh import manifest
    except ImportError:
        logging.debug("compatible emane python bindings not installed")


def _type_value(config_type):
    """
    Convert emane configuration type to core configuration value.

    :param str config_type: emane configuration type
    :return:
    """
    config_type = config_type.upper()
    if config_type == "DOUBLE":
        config_type = "FLOAT"
    elif config_type == "INETADDR":
        config_type = "STRING"
    return ConfigDataTypes[config_type]


def _get_possible(config_type, config_regex):
    """
    Retrieve possible config value options based on emane regexes.

    :param str config_type: emane configuration type
    :param str config_regex: emane configuration regex
    :return: a string listing comma delimited values, if needed, empty string otherwise
    :rtype: list
    """
    if config_type == "bool":
        return ["On", "Off"]

    if config_type == "string" and config_regex:
        possible = config_regex[2:-2]
        return possible.split("|")

    return []


def _get_default(config_type_name, config_value):
    """
    Convert default configuration values to one used by core.

    :param str config_type_name: emane configuration type name
    :param list config_value: emane configuration value list
    :return: default core config value
    :rtype: str
    """

    config_default = ""

    if config_type_name == "bool":
        if config_value and config_value[0] == "true":
            config_default = "1"
        else:
            config_default = "0"
    elif config_value:
        config_default = config_value[0]

    if config_default is None:
        config_default = ""
    return config_default


def parse(manifest_path, defaults):
    """
    Parses a valid emane manifest file and converts the provided configuration values into ones used by core.

    :param str manifest_path: absolute manifest file path
    :param dict defaults: used to override default values for configurations
    :return: list of core configuration values
    :rtype: list
    """

    # no results when emane bindings are not present
    if not manifest:
        return []

    # load configuration file
    manifest_file = manifest.Manifest(manifest_path)
    manifest_configurations = manifest_file.getAllConfiguration()

    configurations = []
    for config_name in sorted(manifest_configurations):
        config_info = manifest_file.getConfigurationInfo(config_name)

        # map type to internal config data type value for core
        config_type = config_info.get("numeric")
        if not config_type:
            config_type = config_info.get("nonnumeric")
        config_type_name = config_type["type"]
        config_type_value = _type_value(config_type_name)

        # get default values, using provided defaults
        if config_name in defaults:
            config_default = defaults[config_name]
        else:
            config_value = config_info["values"]
            config_default = _get_default(config_type_name, config_value)

        # map to possible values used as options within the gui
        config_regex = config_info.get("regex")
        possible = _get_possible(config_type_name, config_regex)

        # define description and account for gui quirks
        config_descriptions = config_name
        if config_name.endswith("uri"):
            config_descriptions = "%s file" % config_descriptions

        configuration = Configuration(
            _id=config_name,
            _type=config_type_value,
            default=config_default,
            options=possible,
            label=config_descriptions,
        )
        configurations.append(configuration)

    return configurations
