# Ansible Core Simulator

A comprehensive simulation of Ansible's architecture and components.

## Contents

- `simulator/` - Core simulation infrastructure (network, machines, resources)
- `ansible_simulator/` - Ansible-specific simulation components

## Running Simulations

### Main Ansible Simulation

```bash
uv run ansible-sim
```

### Strategy Comparison

```bash
uv run ansible-sim-strategy-compare
```

### Integration Test

```bash
uv run ansible-sim-integration-test
```

## Documentation

See `ansible_simulator/README.md` for detailed documentation of the Ansible simulator.
