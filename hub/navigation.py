"""Shared primary navigation and the three Explore views."""

EXPLORE_VIEWS = (('/explore', 'Microbes & genomes'),
                 ('/mechanisms', 'Mechanisms'), ('/conditions', 'Conditions'))
SECTIONS = (('/', 'Learn'), ('/explore', 'Explore'),
            ('/research', 'Research'), ('/references', 'References'))


def primary(active='Learn'):
    return '<nav class="site-nav" aria-label="Atlas">' + ''.join(
        f'<a href="{path}"' + (' aria-current="page"' if name == active else '') + f'>{name}</a>'
        for path, name in SECTIONS
    ) + '</nav>'


def exploring(path='/explore'):
    if path.startswith('/condition/'):
        path = '/conditions'
    return '<nav class="explore-navigation" aria-label="Explore views">' + ''.join(
        f'<a href="{href}"' + (' aria-current="page"' if path == href else '') + f'>{title}</a>'
        for href, title in EXPLORE_VIEWS
    ) + '</nav>'


def active_section(path):
    if path in ('/research', '/papers', '/evidence'):
        return 'Research'
    if path == '/references':
        return 'References'
    if path in ('/explore', '/mechanisms', '/conditions') or path.startswith('/condition/'):
        return 'Explore'
    return 'Learn'
