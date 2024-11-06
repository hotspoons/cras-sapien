
from pydantic.dataclasses import dataclass
from dataclasses import field
import inspect
from enum import Enum
from typing import Callable, Optional

from graph_data import StepData

# TODO - these should point to native handlers, and duplication
# should be removed from Automata

DEFAULT_INPUT_HANDLER = ''
DEFAULT_OUTPUT_HANDLER = ''
DEFAULT_DATA_HANDLER = ''
DEFAULT_SYSTEM_PROMPT_HANDLER = DEFAULT_INPUT_HANDLER

class MediaType(Enum):
    STRING = "STRING"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"
    ANY = "ANY"
    
    def __str__(self):
        return self.name
    
    @classmethod
    def from_string(cls, value):
        return cls[value]

class Ops(Enum):
    GENERATE = "GENERATE"
    DATA_PROCCESS = "DATA_PROCCESS"
    PASSTHROUGH = "PASSTHROUGH"
    # TODO - rank, retrieve, other ops

class AutomataType(Enum):
    # Input and output
    STEP = "STEP"
    # Holds one or more child automata, and can loop until a condition is met
    # in the loopback handler and it returns true
    GRAPH = "GRAPH"

@dataclass(kw_only=True)
class AutomataConfig:
    
    # By default, merge previous step datas and concat outputs
    def default_data_handler(step_datas: list[StepData], initial_input: str) -> tuple[dict, str]:
        output_dict = {}
        output_str_list = []
        # TODO sort or anything?
        for step_data in step_datas:
            output_dict = output_dict | step_data.output_data
            output_str_list.append(step_data.text)
        output_str = initial_input if initial_input != None else "\n".join(output_str_list)
        return output_dict, output_str
    
    name: str = ""
    # Optional ID to differ from name, must be unique
    id: Optional[str] = name
    # Set this to inherit properties from another node. For graphs, will not
    # inherit children, only the graph's properties. Cannot override ops or
    # type
    parent_id: Optional[str] = None
    # Set to the graph ID of the wrapping graph; if none, implicit root-level graph
    graph_id: Optional[str] = None
    # If disabled, inputs and outputs will be directly connected and the node bypassed
    enabled: Optional[bool] = True
    # Initial enabled state, will be used to reset the enablement state so graphs can 
    # turn steps on and off
    initial_enabled_state: bool = True
    # If enabled, assume a socket is present and announce; wait for input; and return output
    socket: Optional[bool] = False
    # If allow failure is true, downstream jobs will execute and ignore
    # output from this step
    allow_failure: Optional[bool] = False
    # An optional list of tags, to aid with defining graphs
    tags: Optional[list[str]] = field(default_factory=list)
    # The type of graph node, defaults to step
    automata_type: Optional[AutomataType] = AutomataType.STEP
    media_type: Optional[list[MediaType]] = field(default_factory=lambda: [MediaType.STRING])
    # An op that will be performed in this automata, defaults to GENERATE
    op: Optional[Ops] = field(default_factory=lambda: Ops.GENERATE)
    # TODO - provide a prefix names like 'tag::'
    # to build graphs based on tags, not only IDs
    # Define upstream nodes in the graph by their ID
    needs: Optional[list[str]] = field(default_factory=list)
    # A dictionary to provide global configuration to all data 
    # processing/handler steps
    global_config: Optional[dict] = field(default_factory=dict)
    max_iterations: Optional[int] = 0
    
    def get_id(self) -> str:
        if self.id == '':
            return self.name
        return self.id
        
    @classmethod
    def from_dict(cls, args):
        inst = cls(**{
            k: v for k, v in args.items() 
            if k in inspect.signature(cls).parameters
        })
        inst.initial_enabled_state = inst.enabled
        return inst
    
@dataclass(kw_only=True)
class AutomataDataProcessorConfig(AutomataConfig):
    # All handlers should either be Python functions in your application,
    # which are passed into the automata initializer in a dictionary of 
    # name -> function reference (prefixed with 'fn:function_name' in configuration),
    # or inline JavaScript functions that will be evaluated as provided.
    #
    # All handlers must take 3 arguments - `data``, which should contain
    # at a minimum a list of data from previous steps on a 'history' key,
    # plus any contextual data to be evaluated within other handlers in
    # the step; `input`, which is raw text input for the handler (such as
    # user-provided input that will be incorporated in a system prompt, or
    # pre-processed user input that can be manipulated in your function); 
    # and config, which is the global automata config provided to all steps.
    
    # All handlers must return an output dictionary of data, which should 
    # contain a data key that includes any changes to the data dictionary
    # passed into the step, as well as an output node, which contains raw
    # string-based data output if provided by the handler.
    
    # All output is forcibly serialized and deserialized to/from JSON to
    # try to force any data quality issues to come out in the serialization
    # step.
    
    # Input handler should have access to all prior output, and can be used
    # to format input from previous steps into an LLM inference step, or to
    # manipulate input for another automata type. 
    #
    # For GROUP-type nodes, this should collect and process the data from any
    # child steps
    # Invoked for DATA_PROCESS, RANK, RETRIEVE and GENERATE ops
    input_handler: Optional[str] = DEFAULT_INPUT_HANDLER
   # On output from an LLM inference, retreival, or plain data processing
    # step, modify the data stream
    # Invoked for DATA_PROCESS, RANK, RETRIEVE and GENERATE ops
    output_handler: Optional[str] = DEFAULT_OUTPUT_HANDLER
    # A list of media types that we want to handle for an automata, defaults to STRING


@dataclass(kw_only=True)
class AutomataGeneratorConfig(AutomataDataProcessorConfig):
    # Override the default model configured for this service; no guarantees 
    # this will work, but allows flexibility
    model: Optional[str] = None
    # For generative nodes, provide a system prompt. 
    # Used with GENERATE op
    system_prompt: Optional[str] = ""
    # System prompt handler can manipulate input prior to it being fed in as
    # the system prompt for input handling, for LLM inference steps. 
    # Invoked for GENERATE op
    system_prompt_handler: Optional[str] = DEFAULT_SYSTEM_PROMPT_HANDLER
    user_prompt: Optional[str] = ""
    # User prompt handler is meant to provide optional massaging of LLM
    # input prior to it being submitted; if no template is provided,
    # the input text will be used from the graph if available, and 
    # any placeholders in the input text (or user_prompt) will be attempted
    # to be filled with data from previous steps step_data.output_data
    user_prompt_handler: Optional[str] = DEFAULT_SYSTEM_PROMPT_HANDLER


class AutomataConfigFactory:
    def __init__(self, config_dict):
        self.automata_config: AutomataConfig = AutomataConfig.from_dict(config_dict)
        self.config = config_dict
    
    def get_config(self) -> AutomataConfig:
        op: Ops = self.automata_config.op
        automata_type: AutomataType = self.automata_config.automata_type
        if op == Ops.DATA_PROCCESS:
            return AutomataDataProcessorConfig.from_dict(self.config)
        elif op == Ops.GENERATE:
            return AutomataGeneratorConfig.from_dict(self.config)
        else:
            return AutomataConfig.from_dict(self.config)
            
                