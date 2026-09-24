def safe_cell(value):
    """Quote untrusted spreadsheet formulas, including whitespace/control prefixes."""
    if not isinstance(value, str):
        return value
    candidate = value.lstrip(" \t\r\n\ufeff")
    if candidate.startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value
