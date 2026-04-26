def explain_addition(a, b):
    actions = []

    # Step 1: set number
    actions.append({"type": "SET_NUMBER", "value": a})

    # Step 2: add
    if b <= 4:
        for _ in range(b):
            actions.append({"type": "ADD_LOWER", "rod": 0})
    else:
        actions.append({"type": "CARRY", "rod": 0})

    return {
        "actions": actions,
        "result": a + b
    }