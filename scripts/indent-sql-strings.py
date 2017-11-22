import argparse
import re


def process_select(lines, index, anchor):
    start = index
    delta = None
    while True:
        where_offset = lines[index].find("WHERE")
        if delta is None and where_offset != -1:
            delta = anchor - (where_offset + 5)
        if '"""' in lines[index]:
            if delta is not None:
                for modify in range(start, index + 1):
                    if delta < 0:
                        assert lines[modify][:-delta] == " " * -delta, lines[modify][
                            :-delta
                        ]
                        lines[modify] = lines[modify][-delta:]
                    else:
                        lines[modify] = " " * delta + lines[modify]
            return index + 1
        index += 1


def process_update(lines, index, anchor):
    start = index
    delta = None
    while True:
        set_offset = lines[index].find("SET")
        if delta is None and set_offset != -1:
            delta = anchor - (set_offset + 3)
            print(
                f"UPDATE: {index} anchor={anchor} set_offset={set_offset} delta={delta}"
            )
        if '"""' in lines[index]:
            if delta is not None:
                for modify in range(start, index + 1):
                    if delta < 0:
                        assert lines[modify][:-delta] == " " * -delta, lines[modify][
                            :-delta
                        ]
                        lines[modify] = lines[modify][-delta:]
                    else:
                        lines[modify] = " " * delta + lines[modify]
            return index + 1
        index += 1


def process_delete(lines, index, anchor):
    start = index
    delta = None
    while True:
        where_offset = lines[index].find("WHERE")
        if delta is None and where_offset != -1:
            delta = anchor - (where_offset + 5)
        if '"""' in lines[index]:
            if delta is not None:
                for modify in range(start, index + 1):
                    if delta < 0:
                        assert lines[modify][:-delta] == " " * -delta, lines[modify][
                            :-delta
                        ]
                        lines[modify] = lines[modify][-delta:]
                    else:
                        lines[modify] = " " * delta + lines[modify]
            return index + 1
        index += 1


def process_insert(lines, index, anchor):
    start = index
    delta = None
    while True:
        if delta is None:
            into_offset = lines[index].find("INTO")
            if into_offset != -1:
                delta = anchor - (into_offset + 4)
            values_offset = lines[index].find("VALUES")
            if values_offset != -1:
                delta = anchor - (values_offset + 6)
        if '"""' in lines[index]:
            if delta is not None:
                for modify in range(start, index + 1):
                    if delta < 0:
                        assert lines[modify][:-delta] == " " * -delta, lines[modify][
                            :-delta
                        ]
                        lines[modify] = lines[modify][-delta:]
                    else:
                        lines[modify] = " " * delta + lines[modify]
            return index + 1
        index += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs="+")

    arguments = parser.parse_args()

    re_begin = re.compile('"""(SELECT|UPDATE|DELETE|INSERT)')

    for filename in arguments.filename:
        with open(filename) as file:
            lines = file.readlines()
        original_lines = lines[:]

        index = 0

        while index < len(lines):
            line = lines[index]
            index += 1
            match = re_begin.search(line)
            if not match:
                continue
            if match.group(1) == "SELECT":
                index = process_select(lines, index, match.end())
            elif match.group(1) == "UPDATE":
                index = process_update(lines, index, match.end())
            elif match.group(1) == "DELETE":
                index = process_delete(lines, index, match.end())
            elif match.group(1) == "INSERT":
                index = process_insert(lines, index, match.end())

        if lines != original_lines:
            print(f"writing {filename}")
            with open(filename, "w") as file:
                file.writelines(lines)


if __name__ == "__main__":
    main()
