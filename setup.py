from distutils.core import setup

setup(
    name='pyopc',
    version='0.1',
    description='Python interface to the Alphasense OPC-N2.',
    url='https://github.com/waggle-sensor/pyopc',
    install_requires=[
        'pyserial'
    ],
    packages=[
        'alphasense',
    ],
)
