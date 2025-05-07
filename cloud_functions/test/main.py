import os


def main():
    print("Hello, world!")

    # Test passing environment variable
    print("TEST_ENV_VAR = ", os.getenv("TEST_ENV_VAR", "[NOT SET]"))


if __name__ == "__main__":
    main()
