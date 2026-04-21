import numpy as np
import math

RED = "\033[31m"
BLUE = "\033[94m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
YELLOW = "\033[33m"
YELLOW2 = "\033[93m"
YELLOW3 = "\033[1;33m"
RESET = "\033[0m"

def get_scan_list_stepped( 
                    min_val:float, 
                    max_val:float, 
                    step:float, 
                    resolution:float=1E-3,
                    margin_pct=0.2,
                    reverse=False,
                    zigzag=True
                    ):
    """
    Generates a scan list based on a fixed step and device resolution.

    Args:
        min_val, max_val: limits of the scan.
        step:             increment between points.
        resolution:       device resolution, to chek the step
        margin_pct:       fraction of step for adding the final boundary point.
                          If (stop - last_point) > step * margin_pct, the 'stop' value is appended.
        reverse:          If True, scan starts from max_val and goes to min_val.
        zigzag:           If True, reorders the list to perform an interleaved scan
                          converts [1,2,3,4,5,6] to [1,3,5,6,4,2].

    Returns:
        list[float]: A sequence of setpoints for the instrument.
    """
    if step < resolution:
        print(f"{RED} get_scan_list_stepped from scan_utils.py: {RESET}")
        raise ValueError(f"Step ({step}) smaller than device resolution ({resolution})")

    if resolution <= 0:
        print(f"{RED} get_scan_list_stepped from scan_utils.py: {RESET}")
        raise ValueError(f"Resolution must be positive, got {resolution}")
    
    if min_val >= max_val:
        print(f"{RED} get_scan_list_stepped from scan_utils.py: {RESET}")
        raise ValueError(f"min_val ({min_val}) must be less than max_val ({max_val})")
    
    if max_val - min_val < step:
        print(f"{RED} get_scan_list_stepped from scan_utils.py: {RESET}")
        raise ValueError(f"max_val - min_val < step")

    start = max_val if reverse else min_val
    stop = min_val if reverse else max_val
    _step = -step if reverse else step

    num_steps = int(abs(max_val - min_val) // step)
    grid = [start + i * _step for i in range(num_steps + 1)]

    remainder = abs(stop - grid[-1])
    if remainder > (step * margin_pct) and remainder > resolution:
        grid.append(stop)

    if zigzag:
        grid = grid[::2] + grid[1::2][::-1]

    return grid


def get_scan_list_linear(
    min_val: float, 
    max_val: float, 
    n_points: int, 
    resolution: float = 1E-3,
    reverse: bool = False,
    zigzag: bool = True
    ):
    """
        Generates a scan list by dividing the range into a fixed number of points.

        Args:
            min_val, max_val: Physical limits of the scan.
            n_points: Total number of points (must be >= 2).
            resolution: Minimum physical step the device can execute.
            reverse: If True, scan starts from max_val.
            zigzag: If True, reorders for interleaved scanning.

        Returns:
            list[float]: A sequence of setpoints for the instrument.
        """
    if n_points < 2:
        print(f"{RED} get_scan_list_linear() from scan_utils.py: {RESET}")
        raise ValueError(f"n_points must be at least 2 (start and end), got {n_points}")
        
    if min_val >= max_val:
        print(f"{RED} get_scan_list_linear() from scan_utils.py: {RESET}")
        raise ValueError(f"min_val ({min_val}) must be less than max_val ({max_val})")

    calc_step = (max_val - min_val) / (n_points - 1)
    if calc_step < resolution:
        print(f"{RED} get_scan_list_linear() from scan_utils.py: {RESET}")
        raise ValueError(
            f"Calculated step ({calc_step:.2E}) is smaller than "
            f"device resolution ({resolution:.2E}). Reduce n_points."
        )
    
    grid = np.linspace(min_val, max_val, n_points).tolist()

    if reverse:
        grid = grid[::-1]

    if zigzag:
        grid = grid[::2] + grid[1::2][::-1]

    decimal_places = int(max(0, -math.log10(resolution)))
    grid = [round(x, decimal_places) for x in grid]

    return grid

## TO DO !!!!!!!!!!!!!!!!!!!!
def get_scan_list(
        scan_type='stepped', # 'linear' 
        **kwards
    ):

    if scan_type == 'stepped':
        step = kwards['step']
        return get_scan_list_stepped(**kwards)
    elif scan_type == 'linear':
        n_points = kwards['n_points']
        return get_scan_list_linear(**kwards)


if __name__ == "__main__":

    def test_get_scan_list_stepped():
        kwards = [
            {'min_val': -13.5, 'max_val': 13.5, "step": 2, 'reverse': False}, 
            {'min_val': -13.5, 'max_val': 13.5, "step": 2, 'reverse': True},
            {'min_val': -13.5, 'max_val': 13.5, "step": 3, 'reverse': False},

        ]

        for k in kwards:
            result = get_scan_list_stepped(**k)
            print(result)
            print()

    test_get_scan_list_stepped()


    def test_get_scan_list_linear():
        kwards = [
            {'min_val': -13.5, 'max_val': 13.5, "n_points": 15, 'reverse': False}, 
            {'min_val': -13.5, 'max_val': 13.5, "n_points": 15, 'reverse': True},
            {'min_val': -13.5, 'max_val': 13.5, "n_points": 9, 'reverse': False},

        ]

        for k in kwards:
            result = get_scan_list_linear(**k)
            print(result)
            print()

    
    test_get_scan_list_linear()
