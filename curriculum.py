def generate_levels():
    levels = []

    for i in range(1, 101):
        if i <= 20:
            t = "addition"
        elif i <= 40:
            t = "addition_carry"
        elif i <= 60:
            t = "subtraction"
        elif i <= 80:
            t = "multiplication"
        else:
            t = "division"

        levels.append({
            "level": i,
            "type": t,
            "range": (1, i)
        })

    return levels