from distutils.core import setup
import just2trade
setup(name='just2trade',
    version=just2trade.__version__,
    description='A Python wrapper around the Just2Trade stock trading API.',
    url='https://github.com/milkybee/just2trade',
    license='LGPL License',
    py_modules=['just2trade'],
    classifiers = [
        "Programming Language :: Python",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    platforms=['OS Independent'],)
