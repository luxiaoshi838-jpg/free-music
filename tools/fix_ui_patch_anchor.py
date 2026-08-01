#!/usr/bin/env python3
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', required=True)
    parser.parse_args()
    print('legacy_patch_preprocessor=noop')


if __name__ == '__main__':
    main()
