def bounded_text(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"Text must be at most {limit} characters.")

    return value.strip()
