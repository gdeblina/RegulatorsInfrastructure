import unittest

from aws_cdk import core

from hello.hello_construct import HelloConstruct

class TestRegulatorsInfrastructureStack(unittest.TestCase):

    def setUp(self):
        self.app = core.App()
        self.stack = core.Stack(self.app, "TestStack")