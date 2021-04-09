# Copyright (c) 2019-2021 Sine Nomine Associates

.PHONY: help init lint test build install clean distclean

PYTHON=/usr/bin/python3
VERSION=1.0.0-rc5
UPDATE=--force

help:
	@echo "usage: make <target>"
	@echo "targets:"
	@echo "  venv        install virtualenv"
	@echo "  lint        run lint checks"
	@echo "  test        run unit and molecule tests"
	@echo "  scenarios   generate molecule scenarios"
	@echo "  build       build openafs collection"
	@echo "  install     install openafs collection"
	@echo "  reset       reset molecule temporary directories"
	@echo "  clean       remove generated files"
	@echo "  distclean   remove generated files and virtualenv"

.venv/bin/activate:
	test -d .venv || $(PYTHON) -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install wheel
	.venv/bin/pip install molecule[ansible] molecule-vagrant molecule-virtup python-vagrant ansible-lint pyflakes pytest
	touch .venv/bin/activate

venv: .venv/bin/activate

builds/openafs_contrib-openafs-$(VERSION).tar.gz:
	mkdir -p builds
	ansible-galaxy collection build --output-path builds .

build: builds/openafs_contrib-openafs-$(VERSION).tar.gz

install: build
	ansible-galaxy collection install $(UPDATE) builds/openafs_contrib-openafs-$(VERSION).tar.gz

lint:
	pyflakes plugins/modules/*.py
	$(MAKE) -C roles/openafs_krbserver lint
	$(MAKE) -C roles/openafs_krbclient lint
	$(MAKE) -C roles/openafs_common lint
	$(MAKE) -C roles/openafs_devel lint
	$(MAKE) -C roles/openafs_server lint
	$(MAKE) -C roles/openafs_client lint

test: test-modules test-roles test-playbooks

test-modules:
	$(MAKE) -C tests test

test-roles:
	$(MAKE) -C roles/openafs_krbserver test
	$(MAKE) -C roles/openafs_krbclient test
	$(MAKE) -C roles/openafs_common test
	$(MAKE) -C roles/openafs_devel test
	$(MAKE) -C roles/openafs_server test
	$(MAKE) -C roles/openafs_client test

test-playbooks:
	$(MAKE) -C tests/playbooks test

reset:
	for r in roles/*; do $(MAKE) -C $$r reset; done
	$(MAKE) -C tests/playbooks reset

clean:
	rm -rf builds
	$(MAKE) -C tests clean

distclean: clean
	rm -rf .venv
