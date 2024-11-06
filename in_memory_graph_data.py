
import copy
from automata.automata import GraphData
from graph_data import StepData
from collections import OrderedDict

class InMemoryGraphData(GraphData):
    data_store: list[StepData] = []
    data_store_dict: OrderedDict[str, StepData] = {}
    
    def __init__(self) -> None:
        self.data_store = InMemoryGraphData.data_store
        self.data_store_dict = InMemoryGraphData.data_store_dict
        GraphData.register_graph_data(self)
        
    def fetch_all_data(self) -> list[StepData]:
        return copy.deepcopy(self.data_store)
    
    def fetch_all_data_dict(self) -> dict[str, StepData]:
        return copy.deepcopy(self.data_store_dict)
        
    def fetch_datas(self, query_dict: dict[str, dict[str, list[int]]]) -> list[StepData]:
        step_datas: list[StepData] = []
        for id, iteration_tree in query_dict.items():
            step_data = self.fetch_data(id, iteration_tree)
            if step_data != None:
                step_datas.append(step_data)
        return step_datas

    # Lots of more efficient ways to do this, this is fine for now
    def fetch_data(self, id: str, iteration_tree: list[int]) -> StepData:
        return copy.deepcopy(self.data_store_dict.get(self._format_id(id, iteration_tree), None))
    
    def fetch_last_data_by_id(self, id: str) -> StepData:
        items = self.fetch_all_data_by_id(id)
        if len(items) > 0:
            return items[0]
        return None
    def fetch_first_data_by_id(self, id: str) -> StepData:
        items = reversed(self.fetch_all_data_by_id(id))
        if len(items) > 0:
            return items[0]
        return None
    def fetch_all_data_by_id(self, id: str) -> StepData:
        output: list[StepData] = []
        for item in self.data_store:
            if item.automata_id == id:
                output.append(item)
        output.sort(key=lambda sd: sd.start)
        return output
    
    def put_data(self, step_data: StepData) -> None:
        self.data_store.append(step_data)
        self.data_store_dict[self._format_id(step_data.automata_id, step_data.iteration_tree)] = step_data
    
    def _format_id(self, id: str, iteration_tree: list[int]) -> str:
        return "{}::{}".format(id, iteration_tree)