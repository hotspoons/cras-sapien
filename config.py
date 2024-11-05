import argparse, os, json, sys, logging, traceback, pathlib
from deepmerge import always_merger
from dotenv import load_dotenv
import oyaml as yaml

class Config():
    instance = None
    
    @classmethod
    def get_instance(cls):
        if cls.instance is None:
            cls.instance = cls()
        return cls.instance

    # TODO - config variables should be elevated to class, and the embedded parameters should
    # only be used to set the config variables in the class, eliminate depenedency on argparse
    def __init__(self):
        load_dotenv()
        self.override_params: dict = {}
        self.parameter_map: dict = None
        self.conf: argparse.Namespace = None
        self.parse_args()
        self.logger = logging.getLogger()
        
        self.socket_announce_message = ""
        
        logging.basicConfig()
        self.logger.setLevel(self.conf.log_level)
 
    """Utility to use hints from path prefix to determine if we should consider it 
    an absolute path (starts with '/'); a path relative to the project codebase (starts
    with './'); or a path relative to the working folder (starts with a file or folder name). 
    We also truncate trailing slashes to normalize paths to reduce work in consumer methods"""
    def normalize_and_resolve_path(self, path: str):
        if path.endswith("/") or path.endswith("\\") and len(path) > 1:
            path = path[:-1]
        if path.startswith("/") or path.startswith("\\") or path.startswith("file:///"):
            return path
        elif path.startswith("./") or path.startswith(".\\"):
            return pathlib.Path(__file__).parent.resolve().as_posix() + "/" + path
        return pathlib.Path().resolve().as_posix() + "/" + path
    
    def merge_override_params_key(self, param_dict_key: str | list[str], override_params: dict = {}) -> dict:
        param_map = self.get_parameter_map().copy()
        if isinstance(param_dict_key, str) and param_dict_key in param_map.keys():
            return always_merger.merge(param_map[param_dict_key], override_params)
        else:
            if param_dict_key is None or len(param_dict_key) == 0:
                raise Exception("Param dict path cannot be null or empty")
            orig_dict_key_list = param_dict_key.copy()
            while len(param_dict_key) > 0 and param_map != None:
                if isinstance(param_map, dict) and param_dict_key[0] in param_map.keys():
                    param_map = param_map[param_dict_key[0]]
                    param_dict_key.pop(0)
                else:
                    param_map = None
            if param_map == None:
                raise Exception("Path to dictionary section [{}] were not accessible with only dictionary keys".format(orig_dict_key_list.join(",")))
            return always_merger.merge(param_map, override_params)

        return params

    """Access the parsed arguments from the CLI directly"""
    def get_conf(self) -> argparse.Namespace:
        return self.conf

    def envar_or_req(self, key, req=True, default=None):
        if os.environ.get(key):
            return {'default': os.environ.get(key)}
        elif default != None:
            return {'default': default}
        else:
            return {'required': req}

    def load_config_file(self, path: str) -> dict|list|str:
        print(path)
        with open(path) as f:
            if path.lower().endswith('.json'):
                return json.load(f)
            elif path.lower().endswith('.yaml') or path.lower().endswith('.yml'):
                return yaml.safe_load(f)
            else:
                raise Exception("A file ending with .yml, .yaml or .json file is required")

    def get_parameter_map(self) -> dict:
        if not self.parameter_map:
            parameter_map_file = self.normalize_and_resolve_path(self.conf.parameter_map_location)
        return always_merger.merge(self.load_config_file(parameter_map_file), self.override_params)

    # TODO remove this, this should be on the client side. Reduce parameters necessary to execute to minimum, write a POC flask API that has all this
    def parse_args(self):
        parser = argparse.ArgumentParser(description='Agent tool to run automata via a command line or API. For any argument values that are paths to directories or files,' +
                                         ' prefixing the path with \'/\' or \'file:///\' will make it an absolute path; prefixing the path with \'./\' with resolve the path' +
                                         ' relative to this codebase; and any other prefix will be relative to the working directory where this program was started')
        parser.add_argument('-C', '--parameter-map-location', help='Location of config map JSON or YAML file (defaults to parameter-map.json in current directory)', 
                            **self.envar_or_req('PARAMETER_MAP_LOCATION', False, './parameter-map.json'))
        parser.add_argument('-c', '--automata-location', help='File containing automata config graph, defaults to \'.automata.yaml\' (in this project)' + 
                            ' - to ', **self.envar_or_req('PROMPTS_LOCATION', False, './automata.yaml'))
        parser.add_argument('-m', '--model-name', help='The model to use with this bot', 
                            **self.envar_or_req('MODEL_NAME', True))
        parser.add_argument('-b', '--base-url', help='The base URL to use for an OpenAPI-compatible model endpoint', 
                            **self.envar_or_req('MODEL_BASE_URL', True))
        parser.add_argument('-a', '--api-key', help='The API key to use for an OpenAPI-compatible model endpoint', 
                            **self.envar_or_req('MODEL_API_KEY', True))
        parser.add_argument('-x', '--extended-parameters', help='Optional JSON map for parameters to override values in parameter-map.json from a CLI argument', 
                            **self.envar_or_req('EXTENDED_PARAMETERS', False, '{}'))
        parser.add_argument('-l', '--log-level', help='Log level (CRITICAL, ERROR, WARNING, INFO, DEBUG)', 
                            **self.envar_or_req('LOG_LEVEL', False, 'INFO'))
        parser.add_argument('-M', '--magic-prefix', help='Magic prefix to bind a client code method name (from dictionary) to a method reference. Defaults to "fn:"', 
                            **self.envar_or_req('MAGIC_PREFIX', False, 'fn:'))
        parser.add_argument('-p', '--port', help='API server port for hosting API. Defaults to zero (disabled), in which case this is only a CLI tool', 
                            type=int, **self.envar_or_req('PORT', False, 0))
        parser.add_argument('-w', '--max-workers', help='Maximum number of worker threads per graph execution, defaults to 8', 
                            type=int, **self.envar_or_req('MAX_WORKERS', False, 8))
        parser.add_argument('-W', '--working-folder', help='Working folder for file operations, defaults to /tmp', 
                            **self.envar_or_req('WORKING_FOLDER', False, '/tmp'))
        try:
            self.conf = parser.parse_args()
            self.override_params = json.loads(self.conf.extended_parameters)
        except:
            traceback.print_exc()
            parser.print_help()
            sys.exit(0)