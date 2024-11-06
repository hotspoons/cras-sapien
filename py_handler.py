import orjson as json
from graph_data import StepData
from RestrictedPython import compile_restricted

from handler import Handler

class PyHandler(Handler):
    HANDLER_PREFIX: str = 'py::'
    HANDLER_REF = 'handler'
   
    @staticmethod
    def get_handler_prefix():
        return PyHandler.HANDLER_PREFIX
   
    @staticmethod
    def set_handler_ref(handler_ref: str):
        PyHandler.handler_ref = handler_ref
    
    def invoke_handler(self, handler: str, input_step_datas: list[StepData], 
                       step_data: StepData, 
                       config: dict, input: str = "") -> None:
        handler = self.format_handler(self.HANDLER_PREFIX, handler)
        locals = {
            'input_step_datas': json.loads(json.dumps(input_step_datas)),
            'step_data': json.loads(json.dumps(step_data)),
            'config': json.loads(json.dumps(config)),
            'input': input,
            'graph_data': Handler.GRAPH_DATA
        }
        byte_code = compile_restricted(handler, '<inline handler>', 'exec')
        exec(byte_code, locals=locals)
        try:
            step_data.output_data = locals['step_data']['output_data']
            step_data.input_data = locals['step_data']['input_data']
            step_data.text = locals['step_data']['text']
        except:
            # TODO log, parse, maybe better handling?
            pass