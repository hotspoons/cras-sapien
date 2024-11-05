
from datetime import datetime
from enum import Enum
import traceback
from typing import Callable
import uuid
from networkx import DiGraph, ancestors, descendants, topological_generations
from automata.automata_config import AutomataConfig, AutomataDataProcessorConfig, AutomataGeneratorConfig, AutomataType, Ops
from config import Config
import orjson as json
from generic_socket import GenericSocket
from graph_data import GraphData, StepData
from handler import Handler
from native_handler import NativeHandler
from sapient import Sapient
import networkx
import concurrent.futures
import copy


#TROUBLESHOOT CORE DUMPS
import faulthandler
faulthandler.enable()

RESERVED_ROOT_ID = '___root___'

            
""" Utility class to carry dependencies between multiple classes """
class AutomataDependencies:
    handlers: dict[str, Handler] = {}
    
    def __init__(self, 
                 config: Config, 
                 automata_configs: list[AutomataConfig],
                 sapient: Sapient,
                 graph_data: GraphData,
                 socket: GenericSocket = GenericSocket(),
                 automata_global_config: dict = {},
                 callbacks: dict[str, Callable[[str, list[StepData], list[StepData], StepData, dict, str], None]] = {},
                 session_id: str| int | uuid.UUID = uuid.uuid4()):
        self.config = config
        self.automata_configs = automata_configs
        self.sapient = sapient
        self.graph_data = graph_data
        self.socket = socket
        self.automata_global_config = automata_global_config
        self.session_id = session_id
        self.input_step_datas: list[StepData] = []
        self.all_step_datas: list[StepData] = []
        self.register_handlers(callbacks)
        
    def register_handlers(self, callbacks: dict[str, Callable[[str, list[StepData], list[StepData], StepData, dict, str], None]]) -> None:
        for cls in Handler.__subclasses__():
            prefix = cls.get_handler_prefix()
            if not prefix in AutomataDependencies.handlers.keys():
                AutomataDependencies.handlers[prefix] = cls()
        # Register callbacks from dictionary
        for key, callback in callbacks:
            NativeHandler.register_callback(key, callback)
            
class AutomataState(Enum):
    INITIALIZED = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    ERROR = 4
    ERROR_IGNORED = 4

class Automata:
    def __init__(self,
                 automata_config: AutomataConfig,
                 dependencies: AutomataDependencies):
        self.dependencies = dependencies
        self.config = dependencies.config
        self.conf = dependencies.config.get_conf()
        self.automata_config =  automata_config
        self.automata_global_config = dependencies.automata_global_config
        self.sapient = dependencies.sapient
        self.socket = dependencies.socket
        self.state: AutomataState = AutomataState.INITIALIZED
        self.step_data: StepData = None
        self.input_step_datas: list[StepData] = None
        self.all_step_datas: list[StepData] = None
        self.handlers = dependencies.handlers
    def _get_user_prompt(self):
        if isinstance(self.automata_config, AutomataGeneratorConfig):
            return self.automata_config.user_prompt
        return None
    def _get_user_prompt_handler(self):
        if isinstance(self.automata_config, AutomataGeneratorConfig):
            handler = self.automata_config.user_prompt_handler
            return handler if handler else NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_USER_PROMPT_HANDLER
        return NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_USER_PROMPT_HANDLER
    def _get_system_prompt(self):
        if isinstance(self.automata_config, AutomataGeneratorConfig):
            return self.automata_config.system_prompt
        return None
    def _get_system_prompt_handler(self):
        if isinstance(self.automata_config, AutomataGeneratorConfig):
            handler = self.automata_config.system_prompt_handler
            return handler if handler else NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_SYSTEM_PROMPT_HANDLER
        return NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_SYSTEM_PROMPT_HANDLER
    def _get_input_handler(self):
        if isinstance(self.automata_config, AutomataDataProcessorConfig) or \
            isinstance(self.automata_config, AutomataGeneratorConfig):
            handler = self.automata_config.input_handler
            return handler if handler else NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_INPUT_HANDLER
        return NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_INPUT_HANDLER
    def _get_output_handler(self):
        if isinstance(self.automata_config, AutomataDataProcessorConfig) or \
            isinstance(self.automata_config, AutomataGeneratorConfig):
            handler = self.automata_config.output_handler
            return handler if handler else NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_OUTPUT_HANDLER
        return NativeHandler.get_handler_prefix() + NativeHandler.DEFAULT_OUTPUT_HANDLER
    # TODO wire up socket data handlers
    def _get_socket_input_handler(self):
        return None
    def _get_socket_output_handler(self):
        return None
    
    # Data processor handler, attempts to use handler in registry; an inline handler; or raises exception
    def _process_data(self, handler: str, input_data: StepData, input: str = "") -> StepData:
        step_data: StepData = input_data
        for handler_prefix, handler_instance in self.handlers.items():
            if handler.startswith(handler_prefix):
                handler_instance.invoke_handler(handler, self.input_step_datas,
                                 self.all_step_datas, step_data,
                                 self.automata_global_config, 
                                 input)
                return step_data
        raise Exception("No registered handler found named {}, returning step_data unchanged. " +
                        "The following native handlers are registered: {} - please check your configuration".format(
            handler, ", ".join(NativeHandler.CALLBACKS.keys())))
            
    def set_input_datas(self, input_step_datas: list[StepData], all_step_datas: list[StepData], initial_input: str) -> None:
        self.input_step_datas = input_step_datas
        self.all_step_datas = all_step_datas
        step_data: StepData = StepData(start=datetime.now(), 
                                  automata_id=self.automata_config.get_id(),
                                  parent_id=self.automata_config.parent_id,
                                  session_id=str(self.dependencies.session_id),
                                  text=initial_input)
        self.step_data = self._process_data(self._get_input_handler(), step_data, initial_input)
        
    def invoke(self) -> dict:
        self.state = AutomataState.IN_PROGRESS
        if self.automata_config.enabled == False or self.automata_config.op == Ops.PASSTHROUGH:
            self.step_data.output_data = self.step_data.input_data
            self.state = AutomataState.COMPLETED
            return
        try:
            # TODO think through this design more
            if self.automata_config.socket:
                self.socket.send(self.config.socket_announce_message.format(session_id=self.dependencies.session_id))
                self.step_data.text = self.socket.recv()
                # TODO input processor for socket
            if self.automata_config.op == Ops.GENERATE:
                self._generate()
            elif self.automata_config.op == Ops.DATA_PROCCESS:
                self.step_data = self._process_data(self._get_output_handler(), self.step_data)
            else:
                self.config.logger.error("No valid ops found")
                raise Exception("Cannot continue, no valid logger found")

            self.state = AutomataState.COMPLETED
            self.step_data.end = datetime.now()
            if self.automata_config.socket:
                # TODO 
                self.socket.send(self._process_data(self._get_output_handler(), self.step_data).text)
        except Exception as e:
            self.config.logger.error(e)
            self.config.logger.error(traceback.format_exc())
            if self.automata_config.allow_failure == True:
                self.state = AutomataState.ERROR_IGNORED
            else:
                self.state = AutomataState.ERROR
    
    # Invoke an LLM or other model. TODO switch on data type to drive method and model selection in Sapient,
    # right now just text. Image generation would be slick 
    def _generate(self) -> tuple[dict|list, str]:
        system_prompt_data: StepData = self._process_data(self._get_system_prompt_handler(), copy.deepcopy(self.step_data), self._get_system_prompt())
        user_prompt_data: StepData = self._process_data(self._get_user_prompt_handler(), copy.deepcopy(self.step_data), self._get_user_prompt())
      
        self.config.logger.debug("System prompt: %s", system_prompt_data.text)
        self.config.logger.debug("User prompt: %s", user_prompt_data.text)
        
        content = self.sapient.invoke_llm(system_prompt_data.text, user_prompt_data.text)
        user_prompt_data.text = content
        self.step_data = self._process_data(self._get_output_handler(), user_prompt_data, content)
        
class AutomataGraph:
    def __init__(self, dependencies: AutomataDependencies):
        self.dependencies = dependencies
        self.config = dependencies.config
        self.automata_configs = dependencies.automata_configs
        self.sapient = dependencies.sapient
        self.graph_data = dependencies.graph_data
        
        self.max_workers: int = self.config.conf.max_workers
        self.subgroups: dict[str, list[Automata]] = {}
        self.root_group: list[Automata] = []
        self.automatons: list[Automata] = []
        self.graphs: dict[str, DiGraph] = {}
        for automata_config in self.automata_configs:
            self.automatons.append(Automata(automata_config, dependencies))
        self.automatons_dict: dict[str, Automata] = {a.automata_config.get_id(): a for a in self.automatons}
        self.abort: bool = False
        self._validate_and_build()

    def _evaluate_automatons_state(self)-> None:
        failed_automata: list = []
        if self.abort == False:
            for automata in self.automatons:
                if automata.state == AutomataState.ERROR:
                    self.abort = True
                    failed_automata.append(automata.automata_config.get_id())
        if self.abort == True:
            if len(failed_automata) > 0:
                error_message = "Error state detected in automata {}, aborting graph execution".format(
                    ", ".join(failed_automata))
            else:
                error_message = "Execution aborted from another group, aborting graph execution"
            self.config.logger.error(error_message)
            raise Exception(error_message)
    
    def _get_iteration_tree(self, iteration_tree: list[int], iteration: int) -> list[int]:
        tree = copy.deepcopy(iteration_tree)
        tree.append(iteration)
        return tree
    
    def _get_previous_generation(self, graph: DiGraph, id: str) -> list[str]:
        generations: list = [sorted(generation) for generation in 
                             topological_generations(graph)]
        last_generation: set[str] = []
        while len(generations) > 0:
            id_list = generations.pop()
            if id in id_list:
                return last_generation
            last_generation = id_list
        return []
            
    def _set_input_for_iteration(self, initial_input: str, graph: DiGraph, 
                                 automata: Automata, iteration_tree: list[int], 
                                 iteration: int) -> None:
        # if automata.automata_config.automata_type == AutomataType.GRAPH:
        #     last_data = self.graph_data
        parents = self._get_previous_generation(graph, automata.automata_config.get_id())
        lookup_dict = {}
        
        for parent in parents:
            lookup_dict[parent] = self._get_iteration_tree(iteration_tree, iteration)
        automata_step_data = self.graph_data.fetch_datas(lookup_dict)
        # For subgraph steps with no input, use the data from the parent graph's node
        if not automata_step_data and automata.automata_config.parent_id is not None:
            automata_step_data = [self.graph_data.fetch_data(automata.automata_config.parent_id, iteration_tree)]
        automata.set_input_datas(automata_step_data, 
                                 self.graph_data.fetch_all_data(), initial_input)

    def run_graph(self, iteration: int = 0, 
                  iteration_tree: list[int] = [], graph_id: str = RESERVED_ROOT_ID, 
                  initial_input: str = None) -> list[Automata]:
        graph: DiGraph = self.graphs[graph_id]
        generations: list = [sorted(generation) for generation in 
                             topological_generations(graph)]
        automatons: list[Automata] = []
        stop = False
        while len(generations) > 0 and stop == False:
            automatons = []
            id_list = generations.pop()
            for id in id_list:
                automata: Automata = self.automatons_dict[id]
                self._set_input_for_iteration(
                        initial_input, graph, automata,
                        iteration_tree, iteration
                    )
                automatons.append(automata)
            self._execute_generation(automatons, iteration, iteration_tree, id)
            for automaton in automatons:
                if automaton.step_data.success == False:
                    stop = True
            if stop == True and graph_id != RESERVED_ROOT_ID:
                iteration += 1
                graph_automaton_config = self.automatons_dict[graph_id].automata_config
                if graph_automaton_config.max_iterations > 0 and \
                    iteration <= graph_automaton_config.max_iterations:
                    return self.run_graph(iteration, iteration_tree, graph_id, initial_input)
            initial_input = None
        return automatons
    
    def _execute_generation(self, automatons: list[Automata], iteration: int, 
                            iteration_tree: list[int], id: str):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            subgraph_futures = []
            tree = self._get_iteration_tree(iteration_tree, iteration)
            self._evaluate_automatons_state()
            futures = []
            for automata in automatons:
                futures.append(executor.submit(automata.invoke))
            for future in concurrent.futures.as_completed(futures):
                future.result()
            for automata in automatons:
                automata.step_data.iteration_tree = tree
                if isinstance(automata.step_data.input_data, dict) and \
                    NativeHandler.GRAPH_DATA_KEY in automata.step_data.input_data:
                    automata.step_data.input_data.pop(NativeHandler.GRAPH_DATA_KEY)
                self.graph_data.put_data(copy.deepcopy(automata.step_data))
            self._evaluate_automatons_state()
            for automata in automatons:
                if automata.automata_config.automata_type == AutomataType.GRAPH:
                    def execute_subgraph():
                        iteration_tree_copy = copy.deepcopy(iteration_tree)
                        iteration_tree_copy.append(iteration)
                        iteration_copy = iteration + 1
                        return self.run_graph(iteration_copy, iteration_tree_copy, automata.automata_config.get_id())
                    subgraph_futures.append(executor.submit(execute_subgraph))
            for future in concurrent.futures.as_completed(subgraph_futures):
                    future.result()
    
    def _validate_and_build(self):
        ids: list[str] = [a.automata_config.get_id() for a in self.automatons]
        dups = set([x for x in ids if ids.count(x) > 1])
        
        errors = []
        if len(dups) > 0:
           errors.append('One or more duplicate IDs were found in the graph; this may mask additional errors until duplicates are eliminated: {}'.format(dups))
        if RESERVED_ROOT_ID in ids:
            errors.append('{} is a reserved ID for the root of the graph, please choose another name/id'.format(RESERVED_ROOT_ID))
        for automata in self.automatons:
            parent_id = automata.automata_config.parent_id
            if parent_id != None:
                if not parent_id in ids:
                    errors.append('Automata subgraph reference "{}" not found in ids {}'.format(parent_id, ids))
                else:
                    if parent_id == automata.automata_config.get_id():
                        errors.append('Circular reference found in subgraph node: "{}"'.format(parent_id))
                    # Populate subgroups if they pass basic validation
                    if not parent_id in self.subgroups.keys():
                        self.subgroups[parent_id] = []
                    self.subgroups[parent_id].append(automata)
            # If this is part of the root graph, append it here
            else:
                self.root_group.append(automata)
            for id in automata.automata_config.needs:
                if not id in ids:
                    errors.append('Automata upstream reference "{}" not found in ids {}'.format(id, ids))
                if id == automata.automata_config.get_id():
                    errors.append('Circular reference found in node: "{}"'.format(id))

        for key in self.subgroups.keys():
            #print(self.automatons_dict)
            if self.automatons_dict[key].automata_config.automata_type != AutomataType.GRAPH:
                errors.append('Subgraph {} was not defined as a graph. Set the automata_type to "GRAPH"'.format(key))
        
        errors = errors + self._build_graphs()
        # TODO - need to figure out how to detect circular references between subgraphs
        if len(errors) > 0:
            raise Exception("The following errors were found in the graph configuration: \n\t - " + "\n\t - ".join(errors))
        # for k, v in self.graphs.items():
        #     print('graph: ' + k)
        #     print('dag: {}'.format(v))
        #     print('topo sort: {}' .format(list(topological_sort(v))))
        #     print('topo gen: {}' .format([sorted(generation) for generation in topological_generations(v)]))
        #     print('trans red: {}' .format(antichains(v)))
        #     print('lex sort: {}' .format(lexicographical_topological_sort(v)))

    def _build_graph(self, name: str, automatons: list[Automata]) -> DiGraph:
        graph = networkx.DiGraph(name=name)
        for automata in automatons:
            automata_config = automata.automata_config
            id = automata_config.get_id()
            graph.add_node(id)
            for upstream_node in automata_config.needs:
                graph.add_edge(id, upstream_node)
        return graph
    
    def _build_graphs(self) -> list[str]:
        errors = []
        self.graphs[RESERVED_ROOT_ID] = self._build_graph(RESERVED_ROOT_ID, self.root_group)
        for id, automatons in self.subgroups.items():
            self.graphs[id] = self._build_graph(RESERVED_ROOT_ID, automatons)
        for id, graph in self.graphs.items():
            if not networkx.is_directed_acyclic_graph(graph):
                errors.append('Graph {} is not a DAG, please correct these cycle(s): '.format(id, 
                    networkx.find_cycle(graph)))
        return errors