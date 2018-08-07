#!/usr/bin/env bash

set -e
ansible-playbook test_defaults.yml

# running a second time to verify playbook's idempotence
set +e
ansible-playbook test_defaults.yml > /tmp/second_run.log
{
    grep -q 'changed=0.*failed=0' /tmp/second_run.log &&
    echo 'Playbook is idempotent'
} || {
    cat /tmp/second_run.log
    echo 'Playbook is **NOT** idempotent'
    exit 1
}
