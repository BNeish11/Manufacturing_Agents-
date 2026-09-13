"""Terminal entry point for the offline demonstration."""

from __future__ import annotations

import argparse
import json

from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.orchestration.workflow import run_line_two_failure
from manufacturing_agents.scenarios.updates import (
    line_three_quality_update,
    product_c_priority_update,
    specialized_part_update,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the manufacturing agent demonstration.")
    parser.add_argument("--approve", action="store_true", help="Simulate human approval of the recovery plan.")
    parser.add_argument("--part-update", action="store_true", help="Apply the specialized-part update.")
    parser.add_argument("--product-c-update", action="store_true", help="Make Product C urgent with lower inventory.")
    parser.add_argument("--line-3-quality-update", action="store_true", help="Place Line 3 on quality hold.")
    args = parser.parse_args()

    state = create_state_of_world()
    result = run_line_two_failure(state, human_approved=args.approve)
    if args.part_update:
        specialized_part_update(state)
    if args.product_c_update:
        product_c_priority_update(state)
    if args.line_3_quality_update:
        line_three_quality_update(state)

    print(json.dumps(result, indent=2, default=lambda value: vars(value)))


if __name__ == "__main__":
    main()
