"""
Depth-related validators / helpers.

  - group_operations: cluster consecutive Z<=0 lines into "operations"
    (cutting sequences) for downstream analysis.
  - profile_operation_depths: cluster operations by their min_z depth
    within a tolerance, returning a sorted depth profile.
"""


def group_operations(parser_output):
    """
    Group consecutive lines where Z <= 0 into "operations" (cutting
    sequences). Returns a list of {start_line, end_line, min_z, max_z}.
    """
    if not isinstance(parser_output, dict):
        raise ValueError("Invalid parser_output")

    lines = parser_output.get("lines")
    if not isinstance(lines, list):
        raise ValueError("Invalid parser_output: 'lines' must be list")

    operations = []
    current_op = None

    for entry in lines:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entry in lines")
        if "line_index" not in entry or "state" not in entry:
            raise ValueError("Malformed entry in parser output")

        idx = entry["line_index"]
        state = entry["state"]
        if not isinstance(state, dict):
            raise ValueError(f"Invalid state at line {idx}")

        z = state.get("Z")

        if z is not None and z <= 0:
            if current_op is None:
                current_op = {
                    "start_line": idx,
                    "end_line": idx,
                    "min_z": z,
                    "max_z": z,
                }
            else:
                current_op["end_line"] = idx
                current_op["min_z"] = min(current_op["min_z"], z)
                current_op["max_z"] = max(current_op["max_z"], z)
        else:
            if current_op is not None:
                operations.append(current_op)
                current_op = None

    if current_op is not None:
        operations.append(current_op)

    return operations


def profile_operation_depths(operations, tolerance=0.01):
    """
    Cluster operations by their min_z depth (within tolerance) and
    return a sorted list of {depth, count} clusters.
    """
    if not isinstance(operations, list):
        raise ValueError("Invalid operations")

    clusters = []

    for op in operations:
        if not isinstance(op, dict):
            raise ValueError("Invalid operation entry")

        depth = op.get("min_z")
        if depth is None:
            continue

        matched = False
        for cluster in clusters:
            if abs(depth - cluster["depth"]) <= tolerance:
                cluster["count"] += 1
                matched = True
                break

        if not matched:
            clusters.append({"depth": depth, "count": 1})

    clusters.sort(key=lambda x: x["depth"])
    return clusters
