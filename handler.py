

from abc import abstractmethod
from graph_data import StepData

class Handler:
    
    @staticmethod
    @abstractmethod
    def get_handler_prefix():
        pass

    @staticmethod
    @abstractmethod
    def set_handler_ref(handler_ref: str):
        pass
    
    @abstractmethod
    def invoke_handler(self, handler: str, input_step_datas: list[StepData], 
                       all_step_datas: list[StepData], step_data: StepData, 
                       config: dict, input: str) -> None:
        pass
    
    def format_handler(self, prefix: str, handler: str) -> str:
        return handler.removeprefix(prefix)
        
      