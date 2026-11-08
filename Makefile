install:
	python tasks.py install

seed:
	python tasks.py seed

train:
	python tasks.py train

eval:
	python tasks.py eval

simulate:
	python tasks.py simulate

types:
	python tasks.py types

dev:
	python tasks.py dev

test:
	python tasks.py test

models:
	python tasks.py models

shots:
	python tasks.py shots

.PHONY: install models seed train eval simulate types dev test shots
