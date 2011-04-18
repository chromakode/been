from setuptools import setup, find_packages

setup(name='been',
      description='A life stream collector.',
      version='0.1',
      author='Max Goodman',
      author_email='c@chromakode.com',
      keywords='feed lifestream',
      license='BSD',
      classifiers=[
          "Programming Language :: Python",
          "Topic :: Internet :: WWW/HTTP",
      ],
      packages=find_packages(),
      install_requires=[
            'feedparser',
            'markdown',
            'CouchDB',
      ],
      entry_points={
          'console_scripts': [
              'been = been.been:main',
          ],
      }
)

