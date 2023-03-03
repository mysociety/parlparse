# coding: utf-8

import termios
import fcntl
import sys
import os


def read_single_keypress():
    fd = sys.stdin.fileno()
    oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
    oldterm = termios.tcgetattr(fd)
    newattr = list(oldterm)
    newattr[3] &= ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(fd, termios.TCSANOW, newattr)
    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
    try:
        ret = ''
        while 1:
            try:
                c = sys.stdin.read(1)
                ret += c
            except IOError:
                if ret:
                    break
    except KeyboardInterrupt:
        ret = None
    finally:
        # restore old state
        termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
    return ret


class Menu(object):
    selected = 0

    def output(self, refresh=False):
        if refresh:
            print('\033[%dA' % (len(self.choices) + 1))
        for i, c in enumerate(self.choices):
            if i == self.selected:
                print('\033[0;34m→', end='')
            else:
                print(' ', end='')
            print(c, end='')
            if i == self.selected:
                print('\033[0m')
            else:
                print()

    def __init__(self, choices):
        self.choices = choices

    def pick(self):
        self.output()
        return self.loop()

    def loop(self):
        while 1:
            char = read_single_keypress()
            if char in (None, '\x1b', 'q', 'Q'):
                return None
            if char == '\x1b[A' and self.selected > 0:
                self.selected -= 1
                self.output(True)
            if char == '\x1b[B' and self.selected < len(self.choices)-1:
                self.selected += 1
                self.output(True)
            if char == '\n':
                return self.selected
            if char >= '1' and char <= '9':
                self.selected = ord(char) - 49
                self.output(True)
