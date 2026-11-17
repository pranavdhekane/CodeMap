"""Command-line entry."""
from .orders import place_order


def main():
    return place_order([[1, 2]])


if __name__ == "__main__":
    main()
