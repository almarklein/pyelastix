"""
Generate docs and update README accordingly.
"""

import os
import pyelastix

text = ''

for name in sorted(dir(pyelastix)):
    # Only generate docs for public functions
    if name.startswith('_'):
        continue
    ob = getattr(pyelastix, name)
    if not callable(ob) or not ob.__doc__:
        continue
    
    doc = '    ' + ob.__doc__.lstrip()
    doc = '\n'.join(line[4:] for line in doc.splitlines())
    if doc.startswith(name):
        text += '### `' + doc.split('\n', 1)[0] + '`\n' + doc.split('\n', 1)[1]
    else:
        text += '### `' + name + '()`\n\n' + doc
    text += '\n\n'


if __name__ == '__main__' and globals().get('__file__'):
    fname = os.path.join(os.path.dirname(pyelastix.__file__), 'README.md')
    t = open(fname, 'rb').read().decode()
    t = t.split('\n----\n')[0]
    t += '\n----\n\n' + text
    open(fname, 'wb').write(t.encode())
else:
    print(text)
