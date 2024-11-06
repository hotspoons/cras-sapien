

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
                       step_data: StepData, 
                       config: dict, input: str) -> None:
        pass
    
    def format_handler(self, prefix: str, handler: str) -> str:
        return handler.removeprefix(prefix)
        
      
    from graph_data import GraphData
    GRAPH_DATA: GraphData
    @staticmethod
    def set_graph_data(graph_data: GraphData):
        Handler.GRAPH_DATA = graph_data