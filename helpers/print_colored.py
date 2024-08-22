# Color codes
RED = "31"
GREEN = "32"
YELLOW = "33"
BLUE = "34"
MAGENTA = "35"
CYAN = "36"
WHITE = "37"


def print_colored(text, color_code):
    print(f"\033[{color_code}m{text}\033[0m")


def print_colored_bold(text, color_code):
    print(f"\033[1;{color_code}m{text}\033[0m")
