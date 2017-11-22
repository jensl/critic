import pickle
import sys


def main():
    print(repr(pickle.load(sys.stdin.buffer)))
