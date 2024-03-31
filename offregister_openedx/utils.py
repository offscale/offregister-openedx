# -*- coding: utf-8 -*-
from re import compile
from string import Template


class OTemplate(Template):
    delimiter = "_0_"
    idpattern = r"[a-z][_a-z0-9]*"


def is_email(s):
    email = compile(r"[^@]+@[^@]+\.[^@]+")
    return email.match(s) is not None


def is_domain(s):
    domain = compile(r"^([a-z0-9-]+.)?([a-z0-9-]+).pl$")
    return domain.match(s) is not None
