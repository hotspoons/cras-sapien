import copy
import orjson as json
from typing import Callable
from graph_data import GraphData, StepData
from collections import defaultdict
from deepmerge import always_merger
from handler import Handler
from jinja2 import Template

class NativeHandler(Handler):
    HANDLER_PREFIX: str = 'native::'
    DEFAULT_INPUT_HANDLER: str = 'default_input_handler'
    DEFAULT_OUTPUT_HANDLER: str = 'default_output_handler'
    DEFAULT_SYSTEM_PROMPT_HANDLER: str = 'default_system_prompt_handler'
    DEFAULT_USER_PROMPT_HANDLER: str = 'default_user_prompt_handler'
    PREVIOUS_STEP_DATA_KEY: str = '__previous_step_data'
    DATA_KEY = 'data'
    DATAS_KEY = 'datas'
    INPUT_TEXT_KEY = 'input_text'
    GRAPH_DATA_KEY = 'graph_data'
    
    CALLBACKS: dict[str, Callable[[str, list[StepData], list[StepData], StepData, dict, str], None]] = {}
    
   
    def __init__(self,):
        super().__init__()
        self.register_default_handlers()
   
    def _struct_to_json(struct: dict|list|str|bool|object|int|float):
        return json.dumps(struct, option=json.OPT_INDENT_2).decode("utf-8")
   
   
    def register_default_handlers(self):
        def default_user_prompt_handler(input_step_datas: list[StepData], 
                             step_data: StepData, config: dict, input: str):
            try:
                if not '{{' + NativeHandler.INPUT_TEXT_KEY + '}}' in input:
                    input = '{{' + NativeHandler.INPUT_TEXT_KEY + '}}\n' + input 
                t = Template(input)
                step_data.text = t.render(step_data.input_data)
            except Exception as e:
                step_data.text = input
                
        # By default, merge all upstream data into a dictionary, and combine text
        def default_input_handler(input_step_datas: list[StepData], 
                             step_data: StepData, config: dict, input: str):
            try:
                in_data = {
                    NativeHandler.INPUT_TEXT_KEY: step_data.text,
                    NativeHandler.DATA_KEY: {},
                    NativeHandler.DATAS_KEY: {},
                    NativeHandler.GRAPH_DATA_KEY: NativeHandler.GRAPH_DATA
                }
                if len(input_step_datas) > 0:
                    # For steps with a single parent input (most), make output data from last
                    # step available on the "data" property
                    for input_step_data in input_step_datas:
                        if len(input_step_datas) == 1:
                            in_data[NativeHandler.DATA_KEY] = input_step_data.output_data
                        # For all steps with one or more parents, make those step datas available on datas[automata_id] 
                        in_data[NativeHandler.DATAS_KEY][input_step_data.automata_id] = input_step_data.output_data
                step_data.input_data = in_data
            except Exception as e:
                pass
            
        def default_output_handler(input_step_datas: list[StepData], 
                             step_data: StepData, config: dict, input: str):
            try:
                out_data = json.loads(input)
                if not isinstance(out_data, dict):
                    out_data = {
                        'data': out_data
                    }
                step_data.output_data = out_data
            except Exception as e:
                step_data.output_data = {}
        
        
        def default_system_prompt_handler(input_step_datas: list[StepData], 
                             step_data: StepData, config: dict, input: str):
            try:
                if not '{{' + NativeHandler.INPUT_TEXT_KEY + '}}' in input:
                    input = '{{' + NativeHandler.INPUT_TEXT_KEY + '}}\n' + input 
                t = Template(input)
                step_data.text = t.render(step_data.input_data)
            except Exception as e:
                step_data.text = input

        self.register_callback(self.DEFAULT_INPUT_HANDLER, default_input_handler)
        self.register_callback(self.DEFAULT_OUTPUT_HANDLER, default_output_handler)
        self.register_callback(self.DEFAULT_SYSTEM_PROMPT_HANDLER, default_system_prompt_handler)
        self.register_callback(self.DEFAULT_USER_PROMPT_HANDLER, default_user_prompt_handler)
        
    @staticmethod
    def get_handler_prefix():
        return NativeHandler.HANDLER_PREFIX
      
    @staticmethod
    def set_handler_ref(handler_ref: str):
        pass
    
    @staticmethod
    def register_callback(name: str, callback: Callable[[str, list[StepData], StepData, dict, str], None]):
        NativeHandler.CALLBACKS[name] = callback
    
    def invoke_handler(self, handler: str, input_step_datas: list[StepData], 
                       step_data: StepData, 
                       config: dict, input: str = "") -> None:
        handler = self.format_handler(self.HANDLER_PREFIX, handler)
        if handler in self.CALLBACKS.keys():
            self.CALLBACKS[handler](input_step_datas=input_step_datas, 
                                    step_data=step_data, 
                                    config=config, 
                                    input=input)
        else:
            raise Exception("Native handler {} not registered, aborting!".format(handler))