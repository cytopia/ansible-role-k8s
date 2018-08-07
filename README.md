# Ansible role: K8s

This role renders an arbitrary number of [Jinja2](http://jinja.pocoo.org/) templates and deploys or removes them to/from Kubernetes cluster.


[![Build Status](https://travis-ci.org/cytopia/ansible-role-k8s.svg?branch=master)](https://travis-ci.org/cytopia/ansible-role-k8s)
[![Version](https://img.shields.io/github/tag/cytopia/ansible-role-k8s.svg)](https://github.com/cytopia/ansible-role-k8s/tags)


## Requirements

* Ansible 2.5
* [openshift](https://pypi.org/project/openshift/) Python package


## Command line variables

Additional variables that can be used (either as `host_vars`/`group_vars` or via command line args):

| Variable     | Description                  |
|--------------|------------------------------|
| `k8s_create` | If set with any value, only deployments to create are executed. |
| `k8s_remove` | If set with any value, only deployments to remove are executed. |
| `k8s_tag`    | Only deployments (create or remove) which have this tag specified in their definition are executed. |
| `k8s_force`  | Force deployment. The existing object will be replaced. |


## Example

**playbook.yml:**
```yaml
- hosts: all
  roles:
    - k8s
  tags:
    - k8s
```
**group_vars/all.yml:**
```yaml
k8s_templates_create:
  - template: path/to/pod1.yml.j2
    tag: stage1
  - template: path/to/pod2.yml.j2
    tags:
      - pod
      - stage2

k8s_templates_remove:
  - template: path/to/ds1.yml.j2
    tag: stage1
  - template: path/to/ds2.yml.j2
    tags:
      - pod
      - stage2
```
**Execute:**
```bash
# Remove and deploy all files
$ ansible-playbook playbook.yml

# Only deploy files
$ ansible-playbook playbook.yml -e k8s_create=1

# Only deploy files with tag stage1
$ ansible-playbook playbook.yml -e k8s_create=1 -e k8s_tag=stage1
```


## Testing

#### Requirements

* Docker
* [yamllint](https://github.com/adrienverge/yamllint)
* [openshift](https://pypi.org/project/openshift/) Python package


#### Run tests

```bash
# Lint the source files
make lint

# Run integration tests with default Ansible version
make test

# Run integration tests with custom Ansible version
make test ANSIBLE_VERSION=2.6
```
