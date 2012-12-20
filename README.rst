================
django-jsgettext
================

It is an improvement to the implementation of django gettext for javascrtipt.

Features:
---------

- Now parse javascript teplates for translatable strings (tested with underscore.template)
- New I18n view more extensible (build on top of CBV) that exposes the djangojs gettext domain
  and djsgettext domain generated for translation scrings from js templates. Aditionaly the performance is
  improved with caching of this view (does not supports by django view as default behavior).


How it works?
-------------

Django ``makemesages`` command generates a djangojs domain po file from ``*.js`` files, ``django-jsgettext``
generates a djgettext domain po file from ``.html`` files (javascript templates) and the new view exposes
the two gettext domains to the javascript.

.. note::
    The new view is created because the primary view of django is monolitic and not permits expose domains distinct than ``djangojs`` and ``django``.

Currently, only is tested with underscore templates. Example:

.. code-block:: html

    <div><%= gettext('sample message') %></div>
    <div><%= ngettext('1 message', 'some messages', num) %></div>
    <div><%= interpolate(gettext('sample %s'), [1]) %></div>


How use it?
-----------

Urls files:

.. code-block:: python

    from djsgettext.views import I18n

    urlpatterns = patterns('',
        url(r'^js-gettext/$', I18n.as_view()),
    )


Collect messages from templates:

.. code-block:: console

    python manage.py jsgettext_makemessages
