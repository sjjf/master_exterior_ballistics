# -*- coding: iso-8859-1 -*-
# Copyright (C) 2005, 2006 Martin von Löwis
# Copyright (C) 2017 Simon Fowler <sjjfowler@gmail.com>
# To Be Licensed to PSF under a Contributor Agreement.
# based on bdist_wininst and bdist_msi
"""
Implements the bdist_wix command.
"""
import subprocess
import os
import sys
from sysconfig import get_python_version

from distutils.core import Command
from distutils.dir_util import remove_tree
from distutils.version import StrictVersion
from distutils.errors import DistutilsExecError
from distutils.errors import DistutilsOptionError
from distutils import log
from distutils.util import get_platform

from uuid import uuid4
import xml.etree.ElementTree as ET


# The Wix schema is not simple, but a significant amount of stuff that's in it
# is either boilerplate or very repetitive. Only a few things are really fiddly
# to deal with.
#
# The core of it is Directories, Components and Features. The actual installed
# files are stored under Components, in a one-to-one mapping (this makes little
# sense to me but it's apparently the accepted way to do it).
#
# Since we want to be able to target multiple different versions of Python we
# need to specify the target directory. Limitations in the installer mean that
# the least painful way to do this is to specify a full installation target for
# each different version, which is then presented to the user as an installable
# feature. Making this work is rather convoluted, requiring a collection of
# properties to be set and directories to be specified based on registry
# searches - properties are set from the result of a registry search, and then
# some additional properties are set based on the values of those initial
# properties, and finally features are enabled or disabled based on the values
# of those properties.
#
# Each feature needs to specify the full list of components, and each component
# can only be referred to a single feature, meaning we need to create different
# components for each of the versioned features. This is another rather silly
# limitation, but it's what we've got to work with.
#
# Wrapping all of this is the Product, which represents the actual installable
# thing. It includes a number of GUID values that should be consistent across
# multiple releases of the product (if they're not specified we'll just create
# new GUIDs every time, but in that case the system won't know that the new
# releases are versions of the same product).
#
# As far as implementing data structures for all of this, we'll just implement
# a class for each of the XML tags, each of which will have methods for adding
# whatever children are relevant, and a method for serialising it
# (recursively). Depending on how it goes it might not even be worth using a
# proper XML library - serialising it manually may be easier.
#
# Right now I don't think there's anything to be gained using inheritance,
# since each variant has unique requirements.
class Wix(object):
    def __init__(self):
        self.wix = ET.Element('Wix', attrib={'xmlns': 'http://schemas.microsoft.com/wix/2006/wi'})
        self.tree = ET.ElementTree(element=self.wix)
        self.children = []

    def add_product(self, name, Id, UpgradeCode, Version, Manufacturer, License):
        p = Product(name, Id, UpgradeCode, Version, Manufacturer, License)
        self.children.append(p)
        return p

    def serialise(self):
        for child in self.children:
            child.serialise(self.wix)
        return self.tree

    def get_tree(self):
        return self.tree


class Product(object):
    def __init__(self, name, Id, UpgradeCode, Version, Manufacturer, License=None):
        self.id = Id
        self.upgrade_code = UpgradeCode
        self.name = name
        self.version = Version
        self.manufacturer = Manufacturer
        self.license = License
        self.children = []

    def add_property(self, Id, value=None):
        p = Property(Id, value)
        self.children.append(p)
        return p

    def add_set_property(self, action, Id, value, condition):
        sp = SetProperty(action, Id, value, condition)
        self.children.append(sp)
        return sp

    def add_set_directory(self, action, Id, value, condition):
        sd = SetDirectory(action, Id, value, condition)
        self.children.append(sd)
        return sd

    def add_directory(self, Id, name):
        d = Directory(Id, name)
        self.children.append(d)
        return d

    def add_feature(self, Id, title, desc, level='1'):
        f = Feature(Id, title, desc, level)
        self.children.append(f)
        return f

    def add_major_upgrade(self, Id,):
        mu = MajorUpgrade(Id)
        self.children.append(mu)
        return mu

    def add_upgrade(self, Id, minver, maxver):
        u = Upgrade(Id, minver, maxver)
        self.children.append(u)
        return u

    def serialise(self, parent):
        # this has a bunch of extra complexity, since there's some boilerplate
        # at this level that's not worth wrapping in a separate class
        attrib = {
            'Name': self.name,
            'Id': str(self.id),
            'UpgradeCode': str(self.upgrade_code),
            'Language': '1033',
            'Codepage': '1252',
            'Version': self.version,
            'Manufacturer': self.manufacturer,
        }
        product = ET.SubElement(parent, 'Product', attrib=attrib)
        attrib = {
            'Id': '*',
            'Keywords': 'Installer',
            'Description': 'bdist_wix installer 0.1.0',
            'Manufacturer': self.manufacturer,
            'InstallerVersion': '100',
            'Languages': '1033',
            'Compressed': 'yes',
            'SummaryCodepage': '1252',
        }
        ET.SubElement(product, 'Package', attrib=attrib)
        attrib = {
            'Id': '1',
            'Cabinet': 'bdist_wix.cab',
            'EmbedCab': 'yes',
            'DiskPrompt': 'CD-ROM #1',
        }
        ET.SubElement(product, 'Media', attrib=attrib)
        attrib = {
            'Id': 'DiskPrompt',
            'Value': 'bdist_wix installation [1]',
        }
        ET.SubElement(product, 'Property', attrib=attrib)
        attrib = {
            'Id': 'WixUI_FeatureTree',
        }
        ET.SubElement(product, 'UIRef', attrib=attrib)
        if self.license:
            attrib = {
                'Id': 'WixUILicenseRtf',
                'Value': self.license,
            }
            ET.SubElement(product, 'WixVariable', attrib=attrib)
        for child in self.children:
            child.serialise(product)


class Directory(object):
    def __init__(self, Id, name):
        self.id = Id
        self.name = name
        # a simple list of children, either more Directories or Components
        self.children = []

    def add_directory(self, Id, name):
        d = Directory(Id, name)
        self.children.append(d)
        return d

    def add_component(self, Id):
        c = Component(Id)
        self.children.append(c)
        return c

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Name': self.name,
        }
        directory = ET.SubElement(parent, 'Directory', attrib=attrib)
        for child in self.children:
            child.serialise(directory)


class Component(object):
    def __init__(self, Id):
        self.id = Id
        # this should always be unique
        self.guid = uuid4()
        self.children = []

    def add_file(self, Id, name, source):
        f = File(Id, name, source)
        self.children.append(f)
        return f

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Guid': str(self.guid),
        }
        component = ET.SubElement(parent, 'Component', attrib=attrib)
        for child in self.children:
            child.serialise(component)


class File(object):
    def __init__(self, Id, name, source):
        self.id = Id
        self.name = name
        self.source = source
        self.children = []

    def add_shortcut(self, Id, directory, name):
        s = Shortcut(Id, directory, name)
        self.children.append(s)
        return s

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Name': self.name,
            'Source': self.source,
            'DiskId': '1',
            'KeyPath': 'yes',
        }
        f = ET.SubElement(parent, 'File', attrib=attrib)
        for child in self.children:
            child.serialise(f)


class Shortcut(object):
    def __init__(self, Id, directory, name):
        self.id = Id
        self.directory = directory
        self.name = name

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Directory': self.directory,
            'Name': self.name,
            'Advertise': 'yes',
        }
        ET.SubElement(parent, 'Shortcut', attrib=attrib)


class Property(object):
    def __init__(self, Id, value=None):
        self.id = Id
        self.value = value
        self.children = []

    def add_registry_search(self, Id, root, key):
        r = RegistrySearch(Id, root, key)
        self.children.append(r)
        return r

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
        }
        if self.value:
            attrib['Value'] = self.value
        prop = ET.SubElement(parent, 'Property', attrib=attrib)
        for child in self.children:
            child.serialise(prop)


class RegistrySearch(object):
    def __init__(self, Id, root, key):
        self.id = Id
        self.root = root
        self.key = key

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Type': 'raw',
            'Root': self.root,
            'Key': self.key,
        }
        ET.SubElement(parent, 'RegistrySearch', attrib=attrib)


class SetProperty(object):
    def __init__(self, action, Id, value, condition):
        self.id = Id
        self.action = action
        self.value = value
        self.condition = condition
        self.stype = None
        self.target = None

    # it'd be nice to be able to specify more than one sequencing datum, but
    # that's not an option
    def set_sequence(self, stype, target):
        self.stype = stype
        self.target = target

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Action': self.action,
            'Value': self.value,
        }
        if self.stype and self.target:
            attrib[self.stype] = self.target
        setprop = ET.SubElement(parent, 'SetProperty', attrib=attrib)
        setprop.text = self.condition


class SetDirectory(object):
    def __init__(self, action, Id, value, condition):
        self.id = Id
        self.action = action
        self.value = value
        self.condition = condition

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Action': self.action,
            'Value': self.value,
        }
        sd = ET.SubElement(parent, 'SetDirectory', attrib=attrib)
        sd.text = self.condition


class Feature(object):
    def __init__(self, Id, title, desc, level='1'):
        self.id = Id
        self.title = title
        self.desc = desc
        self.level = level
        self.children = []

    def add_condition(self, level, condition):
        c = Condition(level, condition)
        self.children.append(c)
        return c

    def add_componentref(self, Id):
        c = ComponentRef(Id)
        self.children.append(c)
        return c

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
            'Title': self.title,
            'Description': self.desc,
            'Display': 'expand',
            'Level': str(self.level),
        }
        feature = ET.SubElement(parent, 'Feature', attrib=attrib)
        for child in self.children:
            child.serialise(feature)


class Condition(object):
    def __init__(self, level, condition):
        self.level = level
        self.condition = condition

    def serialise(self, parent):
        attrib = {
            'Level': self.level,
        }
        condition = ET.SubElement(parent, 'Condition', attrib=attrib)
        condition.text = self.condition


class ComponentRef(object):
    def __init__(self, Id):
        self.id = Id

    def serialise(self, parent):
        attrib = {
            'Id': self.id,
        }
        ET.SubElement(parent, 'ComponentRef', attrib=attrib)


class MajorUpgrade(object):
    def __init__(self, Id):
        self.id = Id

    def serialise(self, parent):
        attrib = {
            'DowngradeErrorMessage': (
                'A newer version of this package is already installed - '
                'please uninstall that version manually if you wish to '
                'install this version'
            ),
        }
        ET.SubElement(parent, 'MajorUpgrade', attrib=attrib)


class Upgrade(object):
    def __init__(self, Id, minver, maxver):
        self.id = Id
        self.minver = minver
        self.maxver = maxver

    def serialise(self, parent):
        # this is a relatively complex one because we're nesting the
        # UpgradeVersion element rather than having a separate class for it

        attrib = {
            'Id': self.id,
        }
        upgrade = ET.SubElement(parent, 'Upgrade', attrib=attrib)

        attrib = {
            'OnlyDetect': 'no',
            'Property': 'PREVIOUSFOUND',
            'Minimum': self.minver,
            'IncludeMinimum': 'yes',
            'Maximum': self.maxver,
            'IncludeMaximum': 'no',
        }
        ET.SubElement(upgrade, 'UpgradeVersion', attrib = attrib)


class bdist_wix (Command):

    description = "create a Microsoft Installer (.msi) binary distribution using the Wix toolkit"

    user_options = [('bdist-dir=', None,
                     "temporary directory for creating the distribution"),
                    ('plat-name=', 'p',
                     "platform name to embed in generated filenames "
                     "(default: %s)" % get_platform()),
                    ('keep-temp', 'k',
                     "keep the pseudo-installation tree around after " +
                     "creating the distribution archive"),
                    ('target-version=', None,
                     "require a specific python version" +
                     " on the target system"),
                    ('no-target-compile', 'c',
                     "do not compile .py to .pyc on the target system"),
                    ('no-target-optimize', 'o',
                     "do not compile .py to .pyo (optimized)"
                     "on the target system"),
                    ('dist-dir=', 'd',
                     "directory to put final built distributions in"),
                    ('skip-build', None,
                     "skip rebuilding everything (for testing/debugging)"),
                    ('install-script=', None,
                     "basename of installation script to be run after"
                     "installation or before deinstallation"),
                    ('pre-install-script=', None,
                     "Fully qualified filename of a script to be run before "
                     "any files are installed.  This script need not be in the "
                     "distribution"),
                    ('shortcut=', None,
                     "Shortcut to add. Format is "
                     "'(start|desktop):<target>:<name>'. (start|desktop) "
                     "indicate the directory to place the shortcut, "
                     "<target> is the target for the shortcut, and <name> is "
                     "the name to give the shortcut"),
                   ]

    boolean_options = ['keep-temp', 'no-target-compile', 'no-target-optimize',
                       'skip-build']

    all_versions = ['2.5', '2.6', '2.7', '2.8', '2.9',
                    '3.0', '3.1', '3.2', '3.3', '3.4',
                    '3.5', '3.6', '3.7', '3.8', '3.9']

#    all_versions = ['2.0', '2.1', '2.2', '2.3', '2.4',
#                    '2.5', '2.6', '2.7', '2.8', '2.9',
#                    '3.0', '3.1', '3.2', '3.3', '3.4',
#                    '3.5', '3.6', '3.7', '3.8', '3.9']
    other_version = 'X'

    def initialize_options(self):
        self.bdist_dir = None
        self.plat_name = None
        self.keep_temp = 0
        self.no_target_compile = 0
        self.no_target_optimize = 0
        self.target_version = None
        self.dist_dir = None
        self.skip_build = None
        self.install_script = None
        self.pre_install_script = None
        self.shortcut = None
        self.license_rtf = None
        self.versions = None

    def finalize_options(self):
        self.set_undefined_options('bdist', ('skip_build', 'skip_build'))

        if self.bdist_dir is None:
            bdist_base = self.get_finalized_command('bdist').bdist_base
            self.bdist_dir = os.path.join(bdist_base, 'wix')

        short_version = get_python_version()
        if (not self.target_version) and self.distribution.has_ext_modules():
            self.target_version = short_version

        if self.target_version:
            self.versions = [self.target_version]
            if not self.skip_build and self.distribution.has_ext_modules()\
               and self.target_version != short_version:
                raise DistutilsOptionError(
                      "target version can only be %s, or the '--skip-build'"
                      " option must be specified" % (short_version,)
                      )
        else:
            self.versions = list(self.all_versions)

        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'),
                                   ('plat_name', 'plat_name'),
                                   )

        if self.pre_install_script:
            raise DistutilsOptionError("the pre-install-script feature is not yet implemented")

        if self.install_script:
            raise DistutilsOptionError("the install-script feature is not yet implemented")

        self.shortcut_dir = self.shortcut_target = self.shortcut_name = None
        if self.shortcut:
            shortcut = self.shortcut.split(':')
            if len(shortcut) < 3:
                raise DistutilsOptionError(
                      "invalid shortcut specification"
                      )
            (self.shortcut_dir, self.shortcut_target, self.shortcut_name) = shortcut
            if self.shortcut_dir != 'start':
                raise DistutilsOptionError("only start menu shortcuts are supported")

        self.install_script_install_key = None
        self.install_script_uninstall_key = None
    # finalize_options()

    def run(self):
        if not self.skip_build:
            self.run_command('build')

        install = self.reinitialize_command('install', reinit_subcommands=1)
        install.prefix = self.bdist_dir
        install.skip_build = self.skip_build
        install.warn_dir = 0

        install_lib = self.reinitialize_command('install_lib')
        # we do not want to include pyc or pyo files
        install_lib.compile = 0
        install_lib.optimize = 0

        if self.distribution.has_ext_modules():
            # If we are building an installer for a Python version other
            # than the one we are currently running, then we need to ensure
            # our build_lib reflects the other Python version rather than ours.
            # Note that for target_version!=sys.version, we must have skipped the
            # build step, so there is no issue with enforcing the build of this
            # version.
            target_version = self.target_version
            if not target_version:
                assert self.skip_build, "Should have already checked this"
                target_version = sys.version[0:3]
            plat_specifier = ".%s-%s" % (self.plat_name, target_version)
            build = self.get_finalized_command('build')
            build.build_lib = os.path.join(build.build_base,
                                           'lib' + plat_specifier)

        log.info("installing to %s", self.bdist_dir)
        install.ensure_finalized()

        # avoid warning of 'install_lib' about installing
        # into a directory not in sys.path
        sys.path.insert(0, os.path.join(self.bdist_dir, 'PURELIB'))

        install.run()

        del sys.path[0]

        self.mkpath(self.dist_dir)
        fullname = self.distribution.get_fullname()
        installer_name = self.get_installer_filename(fullname)
        installer_name = os.path.abspath(installer_name)
        if os.path.exists(installer_name):
            os.unlink(installer_name)

        metadata = self.distribution.metadata
        author = metadata.author
        if not author:
            author = metadata.maintainer
        if not author:
            author = "UNKNOWN"
        version = metadata.get_version()
        # ProductVersion must be strictly numeric
        # XXX need to deal with prerelease versions
        sversion = "%d.%d.%d" % StrictVersion(version).version
        # Prefix ProductName with Python x.y, so that
        # it sorts together with the other Python packages
        # in Add-Remove-Programs (APR)
        fullname = self.distribution.get_fullname()
        if self.target_version:
            product_name = "Python %s %s" % (self.target_version, fullname)
        else:
            product_name = "Python %s" % (fullname)
        self.wix = Wix()
        # Note: these two uuids will need to be supplied externally, since
        # they're persistent across the lifetime of the product
        opts = self.distribution.get_option_dict("wix")
        product_uuid = uuid4()
        if "product_uuid" in opts:
            _, product_uuid = opts["product_uuid"]
        upgrade_uuid = uuid4()
        if "upgrade_uuid" in opts:
            _, upgrade_uuid = opts["upgrade_uuid"]

        if "license_rtf" in opts:
            _, license_rtf = opts["license_rtf"]
        self.product = self.wix.add_product(product_name, product_uuid,
                                            upgrade_uuid,
                                            sversion, author, license_rtf)
        props = [('DistVersion', version)]
        email = metadata.author_email or metadata.maintainer_email
        if email:
            props.append(("ARPCONTACT", email))
        if metadata.url:
            props.append(("ARPURLINFOABOUT", metadata.url))
        if props:
            for (key, val) in props:
                self.product.add_property(key, val)

        # add upgrade support
        self.product.add_major_upgrade(upgrade_uuid)

        # this is very constrained at the moment - a single start menu shortcut
        shortcuts = self.distribution.get_option_dict("wix:shortcuts")
        if "start" in shortcuts:
            _, shortcut = shortcuts["start"]
            # don't override the command line
            if not self.shortcut:
                self.shortcut_dir = "start"
                self.shortcut_target, self.shortcut_name = shortcut.split(':')

        self.root = self.product.add_directory('TARGETDIR', 'SourceDir')
        self.root.add_directory('ProgramMenuFolder', 'Programs')

        self.add_find_python()
        self.add_files()

        t = self.wix.serialise()
        # this is a bit silly, but we need to strip the .msi extension because
        # Wix adds it back in
        installer_base = os.path.basename(installer_name)
        installer_base = os.path.join(self.bdist_dir, installer_base)
        installer_base, _ = os.path.splitext(installer_base)
        wix_file = installer_base + '.wsx'
        wixobj_file = installer_base + '.wixobj'
        if os.path.exists(wix_file):
            os.unlink(wix_file)
        if os.path.exists(wixobj_file):
            os.unlink(wixobj_file)
        with open(wix_file, 'w') as out:
            t.write(out, encoding='windows-1252', xml_declaration=True)

        retval = subprocess.call(['candle.exe', '-out', wixobj_file, wix_file])
        if retval != 0:
            raise DistutilsExecError(
                  "Failed to run candle.exe on " + wix_file
                  )
        light_args = [
            'light.exe',
            '-ext', 'WixUIExtension',
            '-out', installer_name,
            wixobj_file,
        ]
        retval = subprocess.call(light_args)
        if retval != 0:
            raise DistutilsExecError(
                  "Failed to run light.exe on " + wixobj_file
                  )

        if hasattr(self.distribution, 'dist_files'):
            tup = 'bdist_wix', self.target_version or 'any', fullname
            self.distribution.dist_files.append(tup)

        if not self.keep_temp:
            remove_tree(self.bdist_dir, dry_run=self.dry_run)

    def add_files(self):
        self.features = {}
        rootdir = os.path.abspath(self.bdist_dir)

#        root = Directory(db, cab, None, rootdir, "TARGETDIR", "SourceDir")
#        f = Feature(db, "Python", "Python", "Everything",
#                    0, 1, directory="TARGETDIR")

        # The heriarchical nature of the Wix directory structure means that we
        # want to do a depth first directory traversal here. We know we're
        # adding a feature per Python version, and that for each feature we're
        # going to want to add references to all the files, so we're probably
        # best off doing the directory walk at the same point that we're
        # creating the feature.
        for version in self.versions + [self.other_version]:
            target = "INSTALLDIR" + version
            name = "Python" + version
            desc = "Everything - Python " + version
            if version is self.other_version:
                title = "Python from another location"
                level = 2
            else:
                title = "Python %s from registry" % version
                level = 1
            feature = self.product.add_feature(name, title, desc, level)
            feature.add_condition('0', 'Not ' + target)
            dir = self.root.add_directory(target, name)
            # how do we do this . . .
            #
            # We have a top level directory for each target, and within that we
            # traverse the filesystem, starting from the top level of the bdist
            # source dir.

            def make_id(pbase, name):
                p = os.path.join(pbase, name)
                p = p.replace('\\', '_').replace(' ', '_').replace('/', '_').replace('-', '_')
                if p[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_":
                    p = "_" + p
                p = p + "." + version
                if len(p) > 72:
                    p = p[-72:]
                return p

            def recurse_dir(parent, directory):
                pbase = os.path.basename(parent)
                for file in os.listdir(parent):
                    afile = os.path.abspath(os.path.join(parent, file))
                    did = make_id(pbase, file)
                    if os.path.isdir(afile):
                        d = directory.add_directory(did, file)
                        recurse_dir(afile, d)
                    else:
                        cid = make_id(pbase, file)
                        c = directory.add_component(cid)
                        fid = make_id("", file)
                        f = c.add_file(fid, file, afile)
                        if file == self.shortcut_target:
                            sid = make_id('start_', file)
                            f.add_shortcut(sid, 'ProgramMenuFolder', self.shortcut_name)
                        feature.add_componentref(cid)

            recurse_dir(rootdir, dir)

    def add_find_python(self):
        """Adds code to the installer to compute the location of Python.

        Properties PYTHON.MACHINE.X.Y and PYTHON.USER.X.Y will be set from the
        registry for each version of Python.

        Properties INSTALLDIRX.Y will be set from PYTHON.USER.X.Y if defined,
        otherwise from PYTHON.MACHINE.X.Y.

        Properties PYTHONX.Y will be set to INSTALLDIRX.Y\\python.exe"""

        for ver in self.versions:
            install_path = r"SOFTWARE\Python\PythonCore\%s\InstallPath" % ver
            machine_reg = "python.machine." + ver
            user_reg = "python.user." + ver
            machine_prop = "PYTHON.MACHINE." + ver
            user_prop = "PYTHON.USER." + ver
            machine_action = "PythonFromMachine" + ver
            user_action = "PythonFromUser" + ver
            exe_action = "PythonExe" + ver
            install_dir_prop = "INSTALLDIR" + ver
            exe_prop = "PYTHON" + ver
            dir_action = "InstallDir" + ver
            pm = self.product.add_property(machine_prop)
            pm.add_registry_search(machine_reg, 'HKLM', install_path)
            pu = self.product.add_property(user_prop)
            pu.add_registry_search(user_reg, 'HKCU', install_path)
            cond = "%s And Not %s" % (machine_prop, install_dir_prop)
            pfm = self.product.add_set_property(machine_action,
                                                install_dir_prop,
                                                "[" + machine_prop + "]",
                                                cond)
            pfm.set_sequence('Before', exe_action)
            cond = "%s And Not %s" % (user_prop, install_dir_prop)
            pfu = self.product.add_set_property(user_action,
                                                install_dir_prop,
                                                "[" + user_prop + "]",
                                                cond)
            pfu.set_sequence('Before', exe_action)
            exe_val = "[%s]\\python.exe" % (install_dir_prop)
            exe = self.product.add_set_property(exe_action,
                                                exe_prop,
                                                exe_val,
                                                install_dir_prop)
            exe.set_sequence('After', 'AppSearch')
            sd_val = "[%s]" % (install_dir_prop)
            self.product.add_set_directory(dir_action,
                                                install_dir_prop,
                                                sd_val,
                                                install_dir_prop)

    def get_installer_filename(self, fullname):
        # Factored out to allow overriding in subclasses
        if self.target_version:
            base_name = "%s.%s-py%s.msi" % (fullname, self.plat_name,
                                            self.target_version)
        else:
            base_name = "%s.%s.msi" % (fullname, self.plat_name)
        installer_name = os.path.join(self.dist_dir, base_name)
        return installer_name
