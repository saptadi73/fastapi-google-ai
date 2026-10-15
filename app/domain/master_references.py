def reference_storage_column(column):
    """Keep human-readable source fields; store resolved identity separately.

    UUID targets from older configurations remain compatible. The prefix cannot
    collide with user columns (which must start with a letter), and target names
    are already bounded to PostgreSQL's 63-character identifier limit.
    """
    if column.target_type == "uuid":
        return column.target_column
    return "_ref_" + column.target_column[:58]
