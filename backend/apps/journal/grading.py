import math

def grade(checks):
    applicable = [c for c in checks if c["status"] != "na"]
    if not applicable or any(c["status"] == "pending" for c in applicable):
        return {"score": None, "grade": "—"}
    score = math.floor(0.5 + 100 * sum(c["weight"] for c in applicable if c["status"] == "followed") / sum(c["weight"] for c in applicable))
    return {"score": score, "grade": next(letter for minimum, letter in [(90,"A"),(80,"B"),(70,"C"),(60,"D"),(0,"F")] if score >= minimum)}
