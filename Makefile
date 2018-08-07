###
### Variables
###
ANSIBLE_VERSION=2.5


###
### Default
###
help:
	@printf "%s\n\n" "Available commands"
	@printf "%s\n"   "make test             Test the Ansible role"
	@printf "%s\n"   "make lint             Lint source files"
	@printf "%s\n"   "make help             Show help"

test:
	docker run --rm -it \
		-v ${PWD}:/etc/ansible/roles/rolename \
		--workdir /etc/ansible/roles/rolename/tests \
		flaconi/ansible:${ANSIBLE_VERSION} ./support/run-tests.sh

lint:
	yamllint .
