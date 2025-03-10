# -*- coding: utf-8 -*-
from aiida.engine import WorkChain


class SomeWorkChain(WorkChain):

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.outline(
            cls.submit_workchains,
            cls.inspect_workchains,
        )

    def submit_workchains(self):
        for i in range(3):
            future = self.submit(SomeWorkChain)
            key = f'workchain.sub{i}'
            self.to_context(**{key: future})

    def inspect_workchains(self):
        for i in range(3):
            assert self.ctx.workchain[f'sub{i}'].is_finished_ok
