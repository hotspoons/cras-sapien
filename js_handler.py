
import orjson as json
from handler import Handler
from graph_data import StepData
import STPyV8

class JSHandler(Handler):
   HANDLER_PREFIX: str = 'js::'
   HANDLER_REF = 'handler'
   
   @staticmethod
   def get_handler_prefix():
      return JSHandler.HANDLER_PREFIX
   
   @staticmethod
   def set_handler_ref(handler_ref: str):
      JSHandler.handler_ref = handler_ref
   
   def invoke_handler(self, handler: str, input_step_datas: list[StepData], 
                      all_step_datas: list[StepData], step_data: StepData, 
                      config: dict, input: str = "") -> None:
      handler = self.format_handler(self.HANDLER_PREFIX, handler)
      with STPyV8.JSContext() as ctx:
                     out = """
         {handler};
         JSON.stringify({handler_ref}({input_step_datas}, {all_step_datas}, {input}, {config}));
                     """.format(handler_ref = self.handler_ref,
                                input_step_datas=json.dumps(input_step_datas),
                                all_step_datas=json.dumps(all_step_datas),
                                input=json.dumps(input),
                              config=json.dumps(self.automata_global_config), 
                              handler=handler)
      step_data.text = out
      try:
         output = json.loads(ctx.eval(out))
         if isinstance(output, dict):
            step_data.input_data = output.get('input_data', "")
            step_data.output_data = output.get('output_data', {})
            step_data.text = output.get('text', "")
      except:
         # If we can't parse the output data to JSON, the next step will just have to deal with it
         pass