import random
from typing import List, Optional
from pydantic import BaseModel

import logging
logger = logging.getLogger(__name__)


class LoadBalancer(BaseModel):
    id: str = "load_balancer"
    gateway_nodes: List[str] = []  # List of active Gateway Node IDs

    def register_gateway(self, gateway_id: str):
        if gateway_id not in self.gateway_nodes:
            self.gateway_nodes.append(gateway_id)
            logger.info(f"LoadBalancer: Registered Gateway {gateway_id}.")

    def unregister_gateway(self, gateway_id: str):
        if gateway_id in self.gateway_nodes:
            self.gateway_nodes.remove(gateway_id)
            logger.info(f"LoadBalancer: Unregistered Gateway {gateway_id}.")

    def get_next_gateway(self) -> Optional[str]:
        if not self.gateway_nodes:
            return None
        # Simple round-robin or random selection
        return random.choice(self.gateway_nodes)
