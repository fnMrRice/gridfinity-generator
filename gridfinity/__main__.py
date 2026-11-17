"""Optional shared dispatcher: python -m gridfinity baseplate|battery|bin ..."""
import argparse
import importlib
import sys

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(description='Gridfinity OpenSCAD generators')
    parser.add_argument('module',choices=['baseplate','battery','bin'])
    if not argv or argv[0] in ('-h','--help'):
        parser.print_help();return 0
    selected=parser.parse_args(argv[:1]).module
    return importlib.import_module('.'+selected,__package__).main(argv[1:])

if __name__=='__main__':raise SystemExit(main())
