#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre import walk
from calibre.constants import numeric_version
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation


class RecipeDisabled(Exception):
    pass


class RecipeInput(InputFormatPlugin):

    name        = 'Recipe Input'
    author      = 'Kovid Goyal'
    description = _('Download periodical content from the Internet')
    file_types  = {'recipe', 'downloaded_recipe'}
    commit_name = 'recipe_input'

    recommendations = {
        ('chapter', None, OptionRecommendation.HIGH),
        ('dont_split_on_page_breaks', True, OptionRecommendation.HIGH),
        ('use_auto_toc', False, OptionRecommendation.HIGH),
        ('input_encoding', None, OptionRecommendation.HIGH),
        ('input_profile', 'default', OptionRecommendation.HIGH),
        ('page_breaks_before', None, OptionRecommendation.HIGH),
        ('insert_metadata', False, OptionRecommendation.HIGH),
        }

    options = {
        OptionRecommendation(name='test', recommended_value=False,
            help=_(
            'Useful for recipe development. Forces'
            ' max_articles_per_feed to 2 and downloads at most 2 feeds.'
            ' You can change the number of feeds and articles by supplying optional arguments.'
            ' For example: --test 3 1 will download at most 3 feeds and only 1 article per feed.')),
        OptionRecommendation(name='username', recommended_value=None,
            help=_('Username for sites that require a login to access '
                'content.')),
        OptionRecommendation(name='password', recommended_value=None,
            help=_('Password for sites that require a login to access '
                'content.')),
        OptionRecommendation(name='recipe_specific_option',
            help=_('Recipe specific options.')),
        OptionRecommendation(name='dont_download_recipe',
            recommended_value=False,
            help=_('Do not download latest version of builtin recipes from the calibre server')),
        OptionRecommendation(name='lrf', recommended_value=False,
            help='Optimize fetching for subsequent conversion to LRF.'),
        }

    def convert(self, recipe_or_file, opts, file_ext, log,
            accelerators):
        listing_recipe_specific_options = 'list' in (opts.recipe_specific_option or ())
        from calibre.web.feeds.recipes import compile_recipe
        opts.output_profile.flow_size = 0
        orig_no_inline_navbars = opts.no_inline_navbars
        if file_ext == 'downloaded_recipe':
            from calibre.utils.zipfile import ZipFile
            zf = ZipFile(recipe_or_file, 'r')
            zf.extractall()
            zf.close()
            with open('download.recipe', 'rb') as f:
                self.recipe_source = f.read()
            recipe = compile_recipe(self.recipe_source)
            recipe.needs_subscription = False
            self.recipe_object = recipe(opts, log, self.report_progress)
        else:
            if os.environ.get('CALIBRE_RECIPE_URN'):
                from calibre.web.feeds.recipes.collection import get_builtin_recipe_by_id, get_custom_recipe
                urn = os.environ['CALIBRE_RECIPE_URN']
                log('Downloading recipe urn: ' + urn)
                rtype, recipe_id = urn.partition(':')[::2]
                if not recipe_id:
                    raise ValueError('Invalid recipe urn: ' + urn)
                if rtype == 'custom':
                    self.recipe_source = get_custom_recipe(recipe_id)
                else:
                    self.recipe_source = get_builtin_recipe_by_id(urn, log=log, download_recipe=not listing_recipe_specific_options)
                if not self.recipe_source:
                    raise ValueError('Could not find recipe with urn: ' + urn)
                if not isinstance(self.recipe_source, bytes):
                    self.recipe_source = self.recipe_source.encode('utf-8')
                recipe = compile_recipe(self.recipe_source)
            elif os.access(recipe_or_file, os.R_OK):
                with open(recipe_or_file, 'rb') as f:
                    self.recipe_source = f.read()
                recipe = compile_recipe(self.recipe_source)
                log('Using custom recipe')
            else:
                from calibre.web.feeds.recipes.collection import get_builtin_recipe_by_title, get_builtin_recipe_titles
                title = getattr(opts, 'original_recipe_input_arg', recipe_or_file)
                title = os.path.basename(title).rpartition('.')[0]
                titles = frozenset(get_builtin_recipe_titles())
                if title not in titles:
                    title = getattr(opts, 'original_recipe_input_arg', recipe_or_file)
                    title = title.rpartition('.')[0]

                raw = get_builtin_recipe_by_title(title, log=log,
                        download_recipe=not opts.dont_download_recipe and not listing_recipe_specific_options)
                builtin = False
                try:
                    recipe = compile_recipe(raw)
                    self.recipe_source = raw
                    if recipe.requires_version > numeric_version:
                        log.warn(
                        'Downloaded recipe needs calibre version at least: {}'.format('.'.join(recipe.requires_version)))
                        builtin = True
                except Exception:
                    log.exception('Failed to compile downloaded recipe. Falling '
                            'back to builtin one')
                    builtin = True
                if builtin:
                    log('Using bundled builtin recipe')
                    raw = get_builtin_recipe_by_title(title, log=log,
                            download_recipe=False)
                    if raw is None:
                        raise ValueError('Failed to find builtin recipe: '+title)
                    recipe = compile_recipe(raw)
                    self.recipe_source = raw
                else:
                    log('Using downloaded builtin recipe')

            if recipe is None:
                raise ValueError(f'{recipe_or_file!r} is not a valid recipe file or builtin recipe')

            disabled = getattr(recipe, 'recipe_disabled', None)
            if disabled is not None:
                raise RecipeDisabled(disabled)
            if listing_recipe_specific_options:
                rso = (getattr(recipe, 'recipe_specific_options', None) or {})
                if rso:
                    log(recipe.title, _('specific options:'))
                    name_maxlen = max(map(len, rso))
                    for name, meta in rso.items():
                        log(' ', name.ljust(name_maxlen), '-', meta.get('short'))
                        if 'long' in meta:
                            from textwrap import wrap
                            for line in wrap(meta['long'], 70 - name_maxlen + 5):
                                log(' '*(name_maxlen + 4), line)
                else:
                    log(recipe.title, _('has no recipe specific options'))
                raise SystemExit(0)
            try:
                ro = recipe(opts, log, self.report_progress)
                ro.download()
            finally:
                from calibre.scraper.simple import cleanup_overseers
                cleanup_overseers()
            self.recipe_object = ro

        for key, val in self.recipe_object.conversion_options.items():
            setattr(opts, key, val)
        opts.no_inline_navbars = orig_no_inline_navbars

        for f in os.listdir('.'):
            if f.endswith('.opf'):
                return os.path.abspath(f)

        for f in walk('.'):
            if f.endswith('.opf'):
                return os.path.abspath(f)

    def postprocess_book(self, oeb, opts, log):
        if self.recipe_object is not None:
            self.recipe_object.internal_postprocess_book(oeb, opts, log)
            self.recipe_object.postprocess_book(oeb, opts, log)

    def specialize(self, oeb, opts, log, output_fmt):
        if opts.no_inline_navbars:
            from calibre.ebooks.oeb.base import XPath
            for item in oeb.spine:
                for div in XPath('//h:div[contains(@class, "calibre_navbar")]')(item.data):
                    div.getparent().remove(div)

    def save_download(self, zf):
        raw = self.recipe_source
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        zf.writestr('download.recipe', raw)
