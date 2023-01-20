SERVICES=bff project node config

lint: $(foreach SVC,$(SERVICES),$(SVC)-lint)
format: $(foreach SVC,$(SERVICES),$(SVC)-format) tests-format common-format

common-format:
	black common
	isort common

tests-format:
	black tests
	isort tests

$(foreach SVC,$(SERVICES),$(SVC)-format): %-format:
	@cd $*-svc && \
	black $* && \
	isort $*

$(foreach SVC,$(SERVICES),$(SVC)-lint): %-lint:
	@cd $*-svc && \
	flake8 $* && \
	mypy $*
