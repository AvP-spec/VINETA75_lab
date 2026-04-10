

class TerminalColours:
    RED = "\033[31m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    YELLOW = "\033[33m"
    YELLOW2 = "\033[93m"
    YELLOW3 = "\033[1;33m"
    RESET = "\033[0m"

    def __init__(self):
        pass

    def print_coulors(self):
        '''
        List avalible coulour names and check visibility on the screen for
        VS code / Spyder or Light / Dark schema
        '''
        print(f"{self.RED} I am RED {self.RESET}")
        print(f"{self.MAGENTA} I am MAGENTA {self.RESET}")
        print(f"{self.BLUE} I am BLUE {self.RESET}")
        print(f"{self.CYAN} I am CYAN {self.RESET}")
        print(f"{self.GREEN} I am GREEN {self.RESET}")
        print(f"{self.YELLOW} I am YELLOW {self.RESET}")
        print(f"{self.YELLOW2} I am YELLOW2 {self.RESET}")
        print(f"{self.YELLOW3} I am YELLOW3 {self.RESET}")



if __name__ == '__main__':
    tc = TerminalColours()
    tc.print_coulors()