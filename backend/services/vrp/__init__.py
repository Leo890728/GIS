"""VRP solving package.

Splits the former monolithic ``garbage_vrp_service`` into focused modules:

- ``payload``: primitive request validators.
- ``geo``: pure geometric helpers.
- ``config``: solve configuration parsing (``_SolveConfig`` / ``_parse_config``).
- ``osrm_client``: OSRM table/nearest/route access and route chunking.
- ``nodes``: pickup/disposal/aggregation/snap node building.
- ``solver``: OR-Tools model setup and solution extraction.
- ``response``: API response assembly.

``garbage_vrp_service`` keeps the public ``solve_garbage_vrp`` orchestration
facade.
"""
