from aws_cdk import (core, aws_codebuild,
                     aws_codecommit,
                     aws_codepipeline,
                     aws_codepipeline_actions, 
                     aws_s3,
                     aws_ssm,
                     aws_ecr,
                     aws_secretsmanager)

class PipelineStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # pipeline requires versioned bucket
        bucket = aws_s3.Bucket(
            self, "SourceBucket",
            bucket_name=f"{props['namespace'].lower()}-{core.Aws.ACCOUNT_ID}",
            versioned=True,
            removal_policy=core.RemovalPolicy.DESTROY
        )

        # ssm parameter to get bucket name later
        bucket_param = aws_ssm.StringParameter(
            self, "ParameterB",
            parameter_name=f"{props['namespace']}-bucket",
            string_value=bucket.bucket_name,
            description='cdk pipeline bucket'
        )

        # ecr repo to push docker container into
        ecr = aws_ecr.Repository(
            self, "ECR",
            repository_name=f"{props['namespace']}",
            removal_policy=core.RemovalPolicy.DESTROY
        )

        # codebuild project meant to run in pipeline to generate CFN stack for the service infrastructure
        cdk_build = aws_codebuild.PipelineProject(
            self, "CdkBuild",
            build_spec=aws_codebuild.BuildSpec.from_object(dict(
                version="0.2",
                phases=dict(
                    install=dict(commands=[
                        "npm install",
                        "npm init"
                    ]),
                    build=dict(commands=[
                        "npm run build",
                        "npm run cdk synth -- -o dist"
                    ])
                ),
                artifacts={
                    "base-directory": "dist",
                    "files": [
                        "ECSStack.template.json"]},
                environment=dict(buildImage=
                    aws_codebuild.LinuxBuildImage.UBUNTU_14_04_NODEJS_10_14_1))
            )
        )

        regulators_docker_build = aws_codebuild.PipelineProject(
            self, "DockerBuild",
            project_name=f"{props['namespace']}-Docker-Build",
            build_spec=aws_codebuild.BuildSpec.from_source_filename(
                filename='docker_build_buildspec.yml'),
            environment=aws_codebuild.BuildEnvironment(
                privileged=True,
            ),

            # pass the ecr repo uri into the codebuild project so codebuild knows where to push
            environment_variables={
                'ecr': aws_codebuild.BuildEnvironmentVariable(
                    value=ecr.repository_uri),
                'tag': aws_codebuild.BuildEnvironmentVariable(
                    value=f"{props['namespace']}")
            },
            description='Pipeline for CodeBuild',
            timeout=core.Duration.minutes(60),
        )

        # codebuild iam permissions to read write s3
        bucket.grant_read_write(regulators_docker_build)
        bucket.grant_read_write(cdk_build)

        # codebuild permissions to interact with ecr
        ecr.grant_pull_push(regulators_docker_build)

        core.CfnOutput(
            self, "ECRURI",
            description="ECR URI",
            value=ecr.repository_uri,
        )
        core.CfnOutput(
            self, "S3Bucket",
            description="S3 Bucket",
            value=bucket.bucket_name
        )

        # define the source artifact
        source_output = aws_codepipeline.Artifact(artifact_name='source')

        # define the build artifact
        cdk_build_output = aws_codepipeline.Artifact(artifact_name='CdkBuild')

        # define the pipeline
        pipeline = aws_codepipeline.Pipeline(
            self, "Pipeline",
            pipeline_name=f"{props['namespace']}-Pipeline",
            artifact_bucket=bucket,
            stages=[
                aws_codepipeline.StageProps(
                    stage_name='Source',
                    actions=[
                        aws_codepipeline_actions.GitHubSourceAction(
                            action_name='GitHubSource',
                            oauth_token=core.SecretValue.secrets_manager('GitHubPersonalAccessTokenForRegulators'),
                            owner='mmerkes',
                            repo='Regulators',
                            output=source_output,
                            trigger=aws_codepipeline_actions.GitHubTrigger.POLL
                        )
                    ]
                ),
                aws_codepipeline.StageProps(
                    stage_name='Build',
                    actions=[
                        aws_codepipeline_actions.CodeBuildAction(
                            action_name='CDK_Build',
                            input=source_output,
                            project=cdk_build,
                            outputs=[cdk_build_output]
                        ),
                        aws_codepipeline_actions.CodeBuildAction(
                            action_name='Regulators_Docker_Build',
                            input=source_output,
                            project=regulators_docker_build
                        )
                    ]
                ),
                aws_codepipeline.StageProps(
                    stage_name='Deploy',
                    actions=[
                        aws_codepipeline_actions.CloudFormationCreateUpdateStackAction(
                            action_name='ECS_CFN_Deploy',
                            template_path=cdk_build_output.at_path(
                                "ECSStack.template.json"),
                            stack_name="RegulatorsECSServiceDeploymentStack",
                            admin_permissions=True
                        )
                    ]
                )    
            ]
        )

        # give pipeline role read write to the bucket
        bucket.grant_read_write(pipeline.role)

        #pipeline param to get the
        pipeline_param = aws_ssm.StringParameter(
            self, "PipelineParam",
            parameter_name=f"{props['namespace']}-pipeline",
            string_value=pipeline.pipeline_name,
            description='cdk pipeline bucket'
        )

        # cfn output
        core.CfnOutput(
            self, "PipelineOut",
            description="Pipeline",
            value=pipeline.pipeline_name
        )

        self.output_props = props.copy()
        self.output_props['ecr'] = ecr