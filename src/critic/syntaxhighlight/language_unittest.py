def find_interpreter():
    from .language import find_interpreter

    interpreter = find_interpreter(["#!/bin/bash", "This is a bash script."])
    assert interpreter == "bash"

    interpreter = find_interpreter(
        ["# This is a Python script.", "But not a valid one, really."]
    )
    assert interpreter is None

    interpreter = find_interpreter(["#!/usr/bin/python", "Another Python script."])
    assert interpreter == "python"

    interpreter = find_interpreter(["#!/usr/bin/python2.7", "Another Python script."])
    assert interpreter == "python2.7"

    interpreter = find_interpreter(["#!/usr/bin/python3", "Another Python script."])
    assert interpreter == "python3"

    interpreter = find_interpreter(["#!/usr/bin/env python", "Another Python script."])
    assert interpreter == "python"

    interpreter = find_interpreter(
        ["#!/usr/bin/env python2.7", "Another Python script."]
    )
    assert interpreter == "python2.7"

    interpreter = find_interpreter(["#!/usr/bin/env python3", "Another Python script."])
    assert interpreter == "python3"

    print("find_interpreter: ok")


def parse_emacs_modeline():
    from .language import parse_emacs_modeline

    modeline = parse_emacs_modeline(
        ["# -*- foo: 10; bar: fie -*-", "Ignore this line."]
    )
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_emacs_modeline(["# -*- foo:10; bar :fie -*-", "Ignore this line."])
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_emacs_modeline(
        ["/* -*- foo: 10; bar: fie -*- */", "Ignore this line."]
    )
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_emacs_modeline(
        ["# This is a modeline:", "# -*- foo: 10; bar: fie -*-", "Ignore this line."]
    )
    assert modeline == {}

    modeline = parse_emacs_modeline(
        ["#!/bin/bash", "# -*- foo: 10; bar: fie -*-", "Ignore this line."]
    )
    assert modeline == {"foo": "10", "bar": "fie"}

    print("parse_emacs_modeline: ok")


def find_emacs_mode():
    from .language import find_emacs_mode

    emacs_mode = find_emacs_mode(["# -*- mode: python -*-", "Ignore this line."])
    assert emacs_mode == "python"

    emacs_mode = find_emacs_mode(["# -*- foo: bar -*-", "Ignore this line."])
    assert emacs_mode is None

    print("find_emacs_mode: ok")


def parse_vim_modeline():
    from .language import parse_vim_modeline

    modeline = parse_vim_modeline(["# vim: foo=10 bar=fie:", "Ignore this line."])
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_vim_modeline(["/* vim: foo=10 bar=fie: */", "Ignore this line."])
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_vim_modeline(["# vim: set foo=10:bar=fie", "Ignore this line."])
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_vim_modeline(
        ["# vim: setlocal foo=10:bar=fie", "Ignore this line."]
    )
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_vim_modeline(
        ["# Ignore this line.", "# vim: foo=10 bar=fie:", "Ignore this line."]
    )
    assert modeline == {"foo": "10", "bar": "fie"}

    modeline = parse_vim_modeline(
        [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "# vim: foo=10 bar=fie:",
            "Ignore this line.",
        ]
    )
    assert modeline == {"foo": "10", "bar": "fie"}

    print("parse_vim_modeline: ok")


def find_vim_filetype():
    from .language import find_vim_filetype

    vim_filetype = find_vim_filetype(["# vim: ft=python :"])
    assert vim_filetype == "python"

    vim_filetype = find_vim_filetype(["# vim: filetype=python :"])
    assert vim_filetype == "python"

    vim_filetype = find_vim_filetype(["# vim: foo=bar :"])
    assert vim_filetype is None

    print("find_vim_filetype: ok")
