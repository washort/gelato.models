from setuptools import setup, find_packages


setup(name='gelato.models',
      version='0.1.2',
      description='Gelato models',
      namespace_packages=['gelato'],
      long_description='',
      author='',
      author_email='',
      license='',
      url='',
      include_package_data=True,
      packages=find_packages(exclude=['tests']),
      install_requires=['django', 'tower'])
