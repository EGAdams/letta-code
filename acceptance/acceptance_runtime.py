from __future__ import annotations

import traceback

from acceptance_steps import dispatch_step


def run_feature(feature):
    failures = []
    executions = 0
    background = feature.get("background") or []
    for scenario in feature.get("scenarios") or []:
        examples = scenario.get("examples") or [{}]
        for example_index, example in enumerate(examples, start=1):
            executions += 1
            world = {}
            name = f'{scenario["name"]}/example_{example_index}'
            try:
                for step in [*background, *(scenario.get("steps") or [])]:
                    dispatch_step(world, step["text"], example)
            except Exception as error:
                failures.append((name, error, traceback.format_exc()))
    for name, error, details in failures:
        print(f"FAIL {name}: {error}")
        print(details)
    if failures:
        print(f"feature={feature.get('name')} total={executions} failed={len(failures)}")
        return 1
    print(f"feature={feature.get('name')} total={executions} passed={executions}")
    return 0
