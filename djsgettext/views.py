# -*- coding: utf-8 -*-

from django.views.decorators.cache import cache_page
from django.views.generic import View
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.text import javascript_quote
from django.utils import six
from django.utils.encoding import smart_text
from django.utils.translation import check_for_language, activate, to_locale, get_language
from django.utils import importlib
from django.conf import settings

import gettext as gettext_module
import os


template_head = """(function() {
    var catalog = {};
"""

template_body = """
    var gettext = function(msgid) {
        var value = catalog[msgid];
        if (typeof(value) == 'undefined') {
            return msgid;
        } else {
            return (typeof(value) == 'string') ? value : value[0];
        }
    };

    var ngettext =(singular, plural, count) {
        value = catalog[singular];
        if (typeof(value) == 'undefined') {
            return (count == 1) ? singular : plural;
        } else {
            return value[pluralidx(count)];
        }
    };

    var pgettext = function(context, msgid) {
        var value = gettext(context + '\\x04' + msgid);
        if (value.indexOf('\\x04') != -1) {
            value = msgid;
        }
        return value;
    };

    var npgettext = function(context, singular, plural, count) {
        var value = ngettext(context + '\\x04' + singular, context + '\\x04' + plural, count);
        if (value.indexOf('\\x04') != -1) {
            value = ngettext(singular, plural, count);
        }
        return value;
    };

    var interpolate = function(fmt, obj, named) {
        if (named) {
            return fmt.replace(/%\(\w+\)s/g, function(match){return String(obj[match.slice(2,-2)])});
        } else {
            return fmt.replace(/%s/g, function(match){return String(obj.shift())});
        }
    };
"""


template_footer = """
    this.gettext = gettext;
    this.ngettext = ngettext;
    this.pgettext = pgettext;
    this.npgettext = npgettext;
    this.interpolate = interpolate;
    this.pluralidx = pluralidx;
}).call(this);
"""

plural_idx_template = """
    var pluralidx = function(n) {
        var v=%s;
        if (typeof(v) == 'boolean') {
            return v ? 1 : 0;
        } else {
            return v;
        }
    };
"""

plural_simple_template = """
    var pluralidx function(count) { return (count == 1) ? 0 : 1; };
"""

I18N_VIEW_CACHE_TIMEOUT = getattr(settings, 'I18N_VIEW_CACHE_TIMEOUT', 20)


class I18n(View):
    domains = ['djsgettext', 'djangojs']
    packages = []

    #@method_decorator(cache_page(I18N_VIEW_CACHE_TIMEOUT))
    def dispatch(self, *args, **kwargs):
        return super(I18n, self).dispatch(*args, **kwargs)

    def get_paths(self, packages):
        paths = []

        for package in packages:
            p = importlib.import_module(package)
            path = os.path.join(os.path.dirname(p.__file__), 'locale')
            paths.append(path)

        paths.extend(list(reversed(settings.LOCALE_PATHS)))
        return paths

    def get_catalog(self, paths):
        default_locale = to_locale(settings.LANGUAGE_CODE)
        locale = to_locale(get_language())

        en_selected = locale.startswith('en')
        en_catalog_missing = True

        t = {}
        for domain in self.domains:
            for path in paths:
                try:
                    catalog = gettext_module.translation(domain, path, ['en'])
                except IOError:
                    continue
                else:
                    if en_selected:
                        en_catalog_missing = False

            if default_locale != 'en':
                for path in paths:
                    try:
                        catalog = gettext_module.translation(domain, path, [default_locale])
                    except IOError:
                        catalog = None

                    if catalog is not None:
                        t.update(catalog._catalog)

            if locale != default_locale:
                if en_selected and en_catalog_missing:
                    t = {}
                else:
                    locale_t = {}
                    for path in paths:
                        try:
                            catalog = gettext_module.translation(domain, path, [locale])
                        except IOError:
                            catalog = None

                        if catalog is not None:
                            locale_t.update(catalog._catalog)

                    if locale_t:
                        t.update(locale_t)
        return t

    def make_js_catalog(self, t):
        items, pitems = [], []
        pdict = {}

        for k, v in t.items():
            if k == '':
                continue
            if isinstance(k, six.string_types):
                items.append("    catalog['%s'] = '%s';\n" % (javascript_quote(k), javascript_quote(v)))
            elif isinstance(k, tuple):
                if k[0] not in pdict:
                    pdict[k[0]] = k[1]
                else:
                    pdict[k[0]] = max(k[1], pdict[k[0]])
                items.append("    catalog['%s'][%d] = '%s';\n" % (javascript_quote(k[0]), k[1], javascript_quote(v)))
            else:
                raise TypeError(k)
        items.sort()

        for k, v in pdict.items():
            pitems.append("    catalog['%s'] = [%s];\n" % (javascript_quote(k), ','.join(["''"]*(v+1))))

        return "".join(items), "".join(pitems)


    def get(self, request):
        packages = self.packages
        if not packages:
            packages = ['django.conf']

        paths = self.get_paths(packages)
        t = self.get_catalog(paths)

        # Plural methods discovery
        plural = None
        plural_template = plural_simple_template

        if '' in t:
            for l in t[''].split('\n'):
                if l.startswith('Plural-Forms:'):
                    plural = l.split(':',1)[1].strip()

        if plural is not None:
            # this should actually be a compiled function of a typical plural-form:
            # Plural-Forms: nplurals=3; plural=n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2;
            plural = [el.strip() for el in plural.split(';') if el.strip().startswith('plural=')][0].split('=',1)[1]
            plural_template = plural_idx_template % (plural)

        catalog, maincatalog = self.make_js_catalog(t)

        src = [template_head, maincatalog, catalog,
            template_body, plural_template, template_footer]

        data = "".join(src)
        return HttpResponse(data, content_type="text/javascript")
