#! $Id: contextexception.py,v 1.12 2004/12/23 12:27:09 goatchurch Exp $
# vim:sw=8:ts=8:et:nowrap


class ContextException(Exception):
    def __init__(self, description, stamp=None, fragment=None):
        self.description = description
        self.stamp = stamp
        self.fragment = fragment

    def __str__(self):
        ret = ""
        if self.fragment is not None:
            ret = ret + "Fragment: " + repr(self.fragment) + "\n\n"
        ret = ret + repr(self.description) + "\n"
        if self.stamp:
            ret = ret + repr(self.stamp) + "\n"
        return ret
