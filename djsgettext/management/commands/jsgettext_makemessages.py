# -*- coding: utf-8 -*-

from django.core.management.commands.makemessages import find_files
from django.core.management.base import CommandError, NoArgsCommand
from optparse import make_option
from subprocess import PIPE, Popen
import os, glob, io, sys


def _popen(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    output, errors = p.communicate()
    return output, errors, p.returncode


class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + (
        make_option('--locale', '-l', default=None, dest='locale',
            help='Creates or updates the message files for the given locale (e.g. pt_BR).'),

        make_option('--all', '-a', action='store_true', dest='all',
            default=False, help='Updates the message files for all existing locales.'),

        make_option('--extension', '-e', dest='extensions',
            help='The file extension(s) to examine (default: "html,txt", or "js" if the domain is "djangojs"). Separate multiple extensions with commas, or use -e multiple times.',
            action='append'),

        make_option('--ignore', '-i', action='append', dest='ignore_patterns',
            default=[], metavar='PATTERN', help='Ignore files or directories matching this glob-style pattern. Use multiple times to ignore more.'),
    )

    domain = 'djsgettext'

    def handle_noargs(self, *args, **options):
        locale = options.get('locale')
        process_all = options.get('all')
        extensions = options.get('extensions')
        verbosity = int(options.get('verbosity'))
        ignore_patterns = options.get('ignore_patterns')
        if options.get('use_default_ignore_patterns'):
            ignore_patterns += ['CVS', '.*', '*~', '*.pyc']
        self.ignore_patterns = list(set(ignore_patterns))

        if not extensions:
            extensions = ['html']
        extensions = [".%s" % (x) for x in extensions]

        return self.make_messages(locale, process_all, extensions, verbosity)

    def make_messages(self, locale, process_all, extensions, verbosity):
        if not os.path.isdir('locale'):
            raise CommandError("This script should be run from django project directory")

        localedir = os.path.abspath('locale')
        locales = []
        if locale is not None:
            locales.append(str(locale))
        elif all:
            locale_dirs = filter(os.path.isdir, glob.glob('%s/*' % localedir))
            locales = [os.path.basename(l) for l in locale_dirs]

        for locale in locales:
            if verbosity > 0:
                sys.stdout.write("processing language %s\n" % locale)

            basedir = os.path.join(localedir, locale, 'LC_MESSAGES')
            if not os.path.isdir(basedir):
                os.makedirs(basedir)

            pofile = os.path.join(basedir, '%s.po' % str(self.domain))
            potfile = os.path.join(basedir, '%s.pot' % str(self.domain))

            # Collect all posible files
            files = []
            for dirpath, file in find_files(".", self.ignore_patterns, verbosity):
                _, file_ext = os.path.splitext(file)
                if file_ext not in extensions:
                    continue

                files.append(os.path.join(dirpath, file))

            # Generate .pot temporal file
            cmd = ("xgettext --language=PHP --from-code=utf-8 -c --keyword=gettext --keyword=ngettext:1,2 "
                   "--keyword=pgettext:1c,2 --keyword=npgettext:1c,2,3 -o {0} {1}")

            cmd = cmd.format(potfile, " ".join(files))
            msgs, errors, status = _popen(cmd)

            msgs, errors, status = _popen('msguniq --to-code=utf-8 "%s"' % (potfile))
            if errors:
                if status != 0:
                    os.unlink(potfile)
                    raise CommandError("errors happened while running msguniq\n%s" % errors)

            if os.path.exists(pofile):
                cmd = "msgmerge -q '%s' '%s' -o '%s'" % (pofile, potfile, pofile)
                msgs, errors, status = _popen(cmd)
                if errors:
                    if status != 0:
                        os.unlink(potfile)
                        raise CommandError("errors happened while running msgmerge\n%s" % errors)
            else:
                with io.open(potfile, "rt") as fpot, io.open(pofile, "wt") as fpo:
                    for line in fpot:
                        if "charset=CHARSET" in line:
                            line = line.replace('charset=CHARSET', 'charset=UTF-8')

                        fpo.write(line)
