from string import Template


class OTemplate(Template):
    delimiter = '_0_'
    idpattern = r'[a-z][_a-z0-9]*'
