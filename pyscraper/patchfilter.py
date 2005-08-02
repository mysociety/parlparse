#! /usr/bin/python2.3
# vim:sw=8:ts=8:et:nowrap

import os
import shutil

def ApplyPatches(filein, fileout, patchfile):
        while True:
                # Apply the patch
                shutil.copyfile(filein, fileout)

                # delete temporary file that might have been created by a previous patch failure
                filoutorg = fileout + ".orig"
                if os.path.isfile(filoutorg):
                    os.remove(filoutorg)
                status = os.system("patch --quiet %s <%s" % (fileout, patchfile))

                if status == 0:
                        return True

                print "blanking out failed patch %s" % patchfile
                os.rename(patchfile, patchfile + ".old~")
                blankfile = open(patchfile, "w")
                blankfile.close()
                

