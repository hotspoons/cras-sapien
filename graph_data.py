from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from collections import OrderedDict
import inspect

@dataclass(kw_only=True)
class StepData:
    input_data: dict = None
    failure_data: dict = None
    output_data: dict = None
    text: str = ""
    start: datetime = None
    end: datetime = None
    automata_id: str = ""
    session_id: str = None
    parent_id: str = None
    iteration_tree: list[int] = field(default_factory=list)
    # Success is false if a step fails
    success: bool = True
    
    @classmethod
    def from_dict(cls, args):
        return cls(**{
            k: v for k, v in args.items() 
            if k in inspect.signature(cls).parameters
        })

class GraphData:
    
    @abstractmethod
    def fetch_all_data(self) -> list[StepData]:
        pass
    @abstractmethod
    def fetch_all_data_dict(self) -> OrderedDict[str, StepData]:
        pass
    @abstractmethod
    def fetch_datas(self, query_dict: dict[str, list[int]]) -> list[StepData]:
        pass
    @abstractmethod
    def fetch_data(self, id: str, iteration_tree: list[int]) -> StepData:
        pass
    @abstractmethod
    def fetch_last_data_by_id(self, id: str) -> StepData:
        pass
    @abstractmethod
    def fetch_first_data_by_id(self, id: str) -> StepData:
        pass
    @abstractmethod
    def fetch_all_data_by_id(self, id: str) -> list[StepData]:
        pass
    @abstractmethod
    def put_data(self, step_data: StepData) -> None:
        pass
    
    
    @staticmethod
    def register_graph_data(instance: GraphData):
        from handler import Handler
        Handler.set_graph_data(instance)