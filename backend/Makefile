VENV ?= $(shell readlink -f ./venv)
HOST_PYTHON ?= python3

export PYTHON = $(VENV)/bin/python3
export PIP = $(VENV)/bin/pip

run: deps
	$(PYTHON) main.py

deps: .requirements.flag

REQUIREMENTS=requirements.txt

freeze: deps
	echo "# freeze $$(date -Is)" >> "$(REQUIREMENTS)"
	$(PIP) freeze >> "$(REQUIREMENTS)"

unfreeze:
	sed -i '/^# freeze/,$$d' "$(REQUIREMENTS)"

.requirements.flag: requirements.txt
	$(HOST_PYTHON) -m venv "$(VENV)"
	$(PIP) install -r $<
	touch $@

clean:
	rm -rf .*.flag $(VENV)

.PHONY: bundle run deps clean
