#!/usr/bin/env python3

from aws_cdk import core

from regulators_infrastructure.regulators_pipeline_stack import PipelineStack
from regulators_infrastructure.regulators_infrastructure_stack import ECSStack

props = {'namespace': 'regulators-service'}
app = core.App()

# stack for pipeline
pipeline = PipelineStack(app, f"{props['namespace']}-pipeline", props, env={'region': 'us-east-1'})

# stack for service infrastructure
ecs_stack = ECSStack(app, f"{props['namespace']}-ecs-deployment", pipeline.output_props)
ecs_stack.add_dependency(pipeline)

app.synth()