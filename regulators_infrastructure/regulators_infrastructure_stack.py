from aws_cdk import (core, aws_ec2 as ec2, aws_ecs as ecs,
                     aws_ecs_patterns as ecs_patterns)

class ECSStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = ec2.Vpc(self, f"{props['namespace'].lower()}-vpc", max_azs=3)

        cluster = ecs.Cluster(self, f"{props['namespace'].lower()}-cluster", vpc=vpc)

        ecs_patterns.ApplicationLoadBalancedFargateService(self, f"{props['namespace'].lower()}",
            cluster=cluster,            # Required
            cpu=512,                    # Default is 256
            desired_count=6,            # Default is 1
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(props['ecr'], f"{props['namespace']}")),
            memory_limit_mib=2048,      # Default is 512
            public_load_balancer=True  # Default is False
        )    