from typing import List, Dict, Callable, Optional
from pydantic import BaseModel
from simulator.infra.machine import Machine

import logging
logger = logging.getLogger(__name__)


class AvailabilityZone(BaseModel):
    id: str
    machines: Dict[str, Machine] = {}
    is_up: bool = True
    _on_fail_callback: Optional[Callable[[str], None]] = None
    _on_recover_callback: Optional[Callable[[str], None]] = None

    class Config:
        arbitrary_types_allowed = True

    def register_callbacks(self, on_fail: Callable[[str], None], on_recover: Callable[[str], None]):
        self._on_fail_callback = on_fail
        self._on_recover_callback = on_recover

    def add_machine(self, machine: Machine):
        self.machines[machine.id] = machine

    def fail(self):
        if self.is_up:
            self.is_up = False
            logger.info(f"Availability Zone {self.id} failed.")
            for machine_id in list(self.machines.keys()):
                self.machines[machine_id].fail()
            if self._on_fail_callback:
                self._on_fail_callback(self.id)

    def recover(self):
        if not self.is_up:
            self.is_up = True
            logger.info(f"Availability Zone {self.id} recovered.")
            for machine_id in list(self.machines.keys()):
                self.machines[machine_id].recover()
            if self._on_recover_callback:
                self._on_recover_callback(self.id)

    def get_available_machines(self) -> List[Machine]:
        return [machine for machine in self.machines.values() if machine.is_up]