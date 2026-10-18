"""Deterministic Treeview widths. Preserve the right-most status column."""

MAIN_COLUMNS = ('field', 'label', 'kind', 'before', 'now', 'state')
MIN_WIDTH = {'field': 116, 'label': 108, 'kind': 54,
             'before': 77, 'now': 84, 'state': 82}
WEIGHTS = {'field': 0.32, 'label': 0.27, 'kind': 0.0,
           'before': 0.20, 'now': 0.21, 'state': 0.0}


def fitted_columns(available: int) -> dict[str, int]:
    """Allocate spare space only to the data columns; state stays visible.

    If the widget gets narrower than the minimum useful content width, Tk's
    horizontal scrollbar handles overflow without shrinking away the status.
    """
    widths = MIN_WIDTH.copy()
    spare = max(0, int(available) - sum(widths.values()) - 4)
    consumed = 0
    keys = ('field', 'label', 'before', 'now')
    for key in keys[:-1]:
        amount = round(spare * WEIGHTS[key])
        widths[key] += amount
        consumed += amount
    widths[keys[-1]] += spare - consumed
    return widths
