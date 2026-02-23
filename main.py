#!/usr/bin/env python3
from config import load_config
from app import HappyCrush


def main():
    HappyCrush(load_config()).run()


if __name__ == "__main__":
    main()
