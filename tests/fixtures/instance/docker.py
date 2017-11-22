from . import Instance


class Docker(Instance):
    def __init__(self, config):
        self.config = config

    def start(self):
        print("docker: starting")

    def stop(self):
        print("docker: stop")
