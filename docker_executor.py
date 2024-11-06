import os
import orjson as json
import docker, logging

from config import Config
from graph_data import StepData
from native_handler import NativeHandler

class DockerExecutor:
    
    app_config = Config.get_instance()

    def docker_build_output_handler(input_step_datas: list[StepData], 
                             step_data: StepData, config: dict, input: str):
        docker_executor = DockerExecutor()
        logs: list[dict] = []
        try:
            id = step_data.session_id
            docker_executor.build_image(os.path.abspath(DockerExecutor.app_config.conf.working_folder) + '/' + id, logs)
        except Exception as e:
            DockerExecutor.app_config.logger.error(e)
        build_summary = ''
        if len(logs) > 0:
            summary = logs[-1]
            if isinstance(summary, dict):
                if 'success' in summary.keys() and summary['success'] == False:
                    step_data.success = False
                if 'output' in summary.keys():
                    build_summary = summary['output']
        step_data.output_data = {
            'build_output': logs,
            'build_summary': build_summary,
            'success': step_data.success
        }
        out_text = []
        for data in step_data.output_data:
            if isinstance(data, str):
                out_text.append(data)
            else:
                out_text.append(json.dumps(data, option=json.OPT_INDENT_2))
        step_data.text = '{summary} \n\n##Build output: ```shell\n{output}\n```'.format(
            summary=step_data.output_data['build_summary'], 
            output='\n'.join(out_text))
    NativeHandler.register_callback('docker_build_output_handler', docker_build_output_handler)
        
    def __init__(self, docker_uri: str = 'unix://var/run/docker.sock'):
        self.client = docker.APIClient(base_url=docker_uri)
        self.logger = logging.getLogger()
                
    def build_image(self, path: str, messages: list[dict]):

        # Build docker image
        self.logger.info('Building docker image ...')
        generator = self.client.build(
            decode=True,
            path=path,
            rm=True,
            network_mode='host',
        )
        while True:
            try:
                output = generator.__next__()
                if isinstance(output, dict):
                    messages.append(output)
                    if 'stream' in output:
                        self.logger.info("Build output: {}".format(output['stream'].strip('\n')))
                    if 'errorDetail' in output:
                        self.logger.error("Build error: {}".format(output['errorDetail']))
                        messages.append({'success': False, 'output': 'Docker build failed - reason: {}'.format(output['errorDetail']['message'])})
                        raise Exception("Could not build image")
            except StopIteration:
                self.logger.info("Complete")
                messages.append({'success': True, 'output': 'Build complete'})
                break
            except ValueError:
                messages.append({'success': False, 'output': output})
                self.logger.info("Error building image: {}".format(output))
                raise Exception("Could not build image")


    